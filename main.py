# Copyright (c) 2021 Linux Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging
import os
import re
import socket
import sys
from pprint import pprint
from time import sleep
from typing import Optional, Union

import numpy as np
import pandas as pd
import psycopg2.extras
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.exc import InterfaceError, OperationalError


def formatDiff(diff):
    duration = str(diff.to_pytimedelta())
    if ('.' in duration):
        duration = duration.split('.')[0]

    if (duration == '0:00:00'):
        return '1st deployment'

    days = ''
    if ('days' in duration):
     days = duration.split(',')[0] + ', '
     duration = duration.split(',')[1]

    parts = duration.split(':')

    hours = parts[0].lstrip(' 0')

    if (hours == ''):
        hours = ''
    else:
       hours = hours + 'h, '

    mins = parts[1].lstrip(' 0')

    if (mins == ''):
        mins = ''
    else:
        mins = mins + 'm '

    return (days + hours + mins).rstrip(', ')

def isBlank (myString):
    return not (myString and myString.strip())

# Init Globals
service_name = 'ortelius-ms-scorecard'
db_conn_retry = 3

app = FastAPI(
    title=service_name,
    description=service_name
)

app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Init db connection
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "postgres")
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASS", "postgres")
db_port = os.getenv("DB_PORT", "5432")
validateuser_url = os.getenv('VALIDATEUSER_URL', None )

if (validateuser_url is None):
    validateuser_host = os.getenv('MS_VALIDATE_USER_SERVICE_HOST', '127.0.0.1')
    host = socket.gethostbyaddr(validateuser_host)[0]
    validateuser_url = 'http://' + host + ':' + str(os.getenv('MS_VALIDATE_USER_SERVICE_PORT', 80))

engine = create_engine("postgresql+psycopg2://" + db_user + ":" + db_pass + "@" + db_host + ":" + db_port + "/" + db_name, pool_pre_ping=True)

# health check endpoint


class StatusMsg(BaseModel):
    status: str
    service_name: Optional[str] = None


@app.get("/health")
async def health(response: Response) -> StatusMsg:
    try:
        with engine.connect() as connection:
            conn = connection.connection
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            if cursor.rowcount > 0:
                return {"status": 'UP', "service_name": service_name}
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": 'DOWN'}

    except Exception as err:
        print(str(err))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": 'DOWN'}
# end health check

class ScoreCard(BaseModel):
    domain: str = ""
    columns: list = None
    data: list = None

@app.get('/msapi/scorecard')
async def getScoreCard(request: Request, domain: Union[str, None] = None, frequency: Union[str, None] = None, env: Union[str, None] = None, lag: Union[str, None] = None, testit: Union[str, None] = None) -> ScoreCard:

    response_data = []
    domname = ""

    try:
        #Retry logic for failed query
        no_of_retry = db_conn_retry
        attempt = 1;
        while True:
            try:
                with engine.connect() as connection:
                    conn = connection.connection
                    cursor = conn.cursor()

                    envorder = []
                    env_cursor = conn.cursor()
                    env_cursor.execute('SELECT envname from dm.dm_env_order order by id asc')
                    rows = env_cursor.fetchall()

                    for row in rows:
                        envorder.append(row[0])

                    if (frequency is not None):
                        data = ScoreCard()

                        # Read data from PostgreSQL database table and load into a DataFrame instance
                        sql = "select application, environment, (weekly::date)::varchar as week, count(weekly) as frequency from dm.dm_app_scorecard " \
                              "group by application, environment, week " \
                              "order by application, environment, week desc"

                        if (domain is not None):
                            cursor2 = conn.cursor()
                            cursor2.execute('SELECT fulldomain(' + str(domain) + ')')
                            if cursor2.rowcount > 0:
                                row = cursor2.fetchone()
                                domname = row[0]
                            cursor2.close()

                            sql = "select application, environment, (weekly::date)::varchar as week, count(weekly) as frequency from dm.dm_app_scorecard " \
                                  "where domainid in (WITH RECURSIVE rec (id) as ( SELECT a.id from dm.dm_domain a where id=" + str(domain) + " UNION ALL SELECT b.id from rec, dm.dm_domain b where b.domainid = rec.id ) SELECT * FROM rec) " \
                                  "group by application, environment, week " \
                                  "order by application, environment, week desc"

                        df = pd.read_sql(sql, connection)

                        table = df.pivot_table('frequency',['application', 'environment', 'week'], 'environment')
                        table = table.fillna('')
                        cols = list(table.columns)

                        newcols = []
                        for env in envorder:
                            if (env in cols):
                                newcols.append(env)
                        missingcols = list(set(cols).difference(set(newcols)))
                        newcols.extend(missingcols)
                        cols = newcols

                        cols.insert(0,'Week')
                        cols.insert(0,'Application')
                        data.columns = []
                        for col in cols:
                            column = {"name": col, "data": col}
                            data.columns.append(column)

                        rows = []
                        # using a itertuples()
                        for i in table.itertuples():
                            row = i.Index
                            rowdict = {}
                            rowdict.update({cols[0]: row[0]})
                            rowdict.update({cols[1]: row[2]})

                            for col in cols[2::]:
                                val = getattr(i, col, None)
                                if (val is None):
                                    key = '_' + str(cols.index(col)-1)
                                    val = getattr(i, key, '')
                                rowdict.update({col: val})
                            rows.append(rowdict)
                        data.data = rows
                        return data
                    elif (lag is not None):
                        data = ScoreCard()
                        # Read data from PostgreSQL database table and load into a DataFrame instance
                        sql = "select application, environment, deploymentid, startts as datetime from dm.dm_app_lag " \
                              "order by application, environment, deploymentid"

                        if (domain is not None):
                            cursor2 = conn.cursor()
                            cursor2.execute('SELECT fulldomain(' + str(domain) + ')')
                            if cursor2.rowcount > 0:
                                row = cursor2.fetchone()
                                domname = row[0]
                            cursor2.close()

                            sql = "select application, environment, deploymentid, startts as datetime from dm.dm_app_lag " \
                                  "where domainid in (WITH RECURSIVE rec (id) as ( SELECT a.id from dm.dm_domain a where id=" + str(domain) + " UNION ALL SELECT b.id from rec, dm.dm_domain b where b.domainid = rec.id ) SELECT * FROM rec) " \
                                  "order by application, environment, deploymentid"

                        df = pd.read_sql(sql, connection)
                        table=df.sort_values(by = ['application', 'environment', 'deploymentid'], ascending = [True, True, True]).groupby(['application', 'environment']).head(2)
                        gs = table.sort_values(by = ['application', 'environment', 'deploymentid'], ascending = [True, True, True]).groupby(['application', 'environment'])['datetime']
                        table['diff'] = gs.diff().fillna(pd.Timedelta(seconds=0))
                        lagtab=table.sort_values(by = ['application', 'environment', 'deploymentid'], ascending = [True, True, False]).groupby(['application', 'environment']).head(1)
                        lagtab['diff'] = lagtab['diff'].apply(formatDiff)
                        lagtab.drop('deploymentid', axis=1, inplace=True)
                        lagtab.drop('datetime', axis=1, inplace=True)
                        table = lagtab.pivot(index=['application'], columns=['environment'], values=['diff']).reset_index()
                        cols = list(table.columns)

                        newcols = [('application', '')]
                        for env in envorder:
                            for key,val in cols:
                                if (key == 'diff' and env == val):
                                    newcols.append((key,val))
                                    continue

                        missingcols = list(set(cols).difference(set(newcols)))
                        newcols.extend(missingcols)
                        table = table.reindex(columns=newcols)

                        table.columns = [ '_'.join(re.findall('.[^A-Z]*',re.sub(r'^diff_','','_'.join(tup).rstrip('_')))) for tup in table.columns.values]
                        table.fillna('', inplace=True)

                        cols = list(table.columns)
                        data.columns = []
                        for col in cols:
                            col = col.lower()
                            column = {"name": col, "data": col}
                            data.columns.append(column)

                        rows = []
                        # using a itertuples()
                        for i in table.itertuples():
                            row = i.Index
                            rowdict = {}

                            for col in cols:
                                val = getattr(i, col, None)
                                if (val is None):
                                    key = '_' + str(cols.index(col)+1)
                                    val = getattr(i, key, '')
                                col = col.lower()
                                rowdict.update({col: val})
                            rows.append(rowdict)

                        data.data = rows
                        data.domain = domname
                        return data
                    else:
                        data = ScoreCard()
                        # Read data from PostgreSQL database table and load into a DataFrame instance
                        sql = "select distinct a.id as appid, b.name as environment from dm_application a, dm_environment b, dm_deployment c where a.id = c.appid and c.envid = b.id order by 1, 2"

                        df = pd.read_sql(sql, connection)
                        envtable = df.pivot(index='appid',columns='environment',values='environment')

                        cols = list(envtable.columns)
                        newcols = []
                        for env in envorder:
                            if (env in cols):
                                newcols.append(env)
                        missingcols = list(set(cols).difference(set(newcols)))
                        newcols.extend(missingcols)
                        envtable = envtable.reindex(columns=newcols)

                        cols = []
                        for col in list(envtable.columns):
                            cols.append('Environment_' + col)
                        envtable.columns = cols

                        sql = "select c.domainid, c.id as appid, b.id as compid, c.name as application, b.name as component, a.name as name, a.value as value " \
                              "from dm.dm_scorecard_nv a, dm.dm_component b, dm.dm_application c, dm.dm_applicationcomponent d " \
                              "where a.id = b.id and b.status = 'N' and c.status = 'N' and a.id = d.compid and c.id = d.appid " \
                              "order by domainid, appid, compid"

                        if (domain is not None):
                            cursor2 = conn.cursor()
                            cursor2.execute('SELECT fulldomain(' + str(domain) + ')')
                            if cursor2.rowcount > 0:
                                row = cursor2.fetchone()
                                domname = row[0]
                            cursor2.close()

                            sql = "select c.domainid, c.id as appid, b.id as compid, c.name as application, b.name as component, a.name as name, a.value as value " \
                                "from dm.dm_scorecard_nv a, dm.dm_component b, dm.dm_application c, dm.dm_applicationcomponent d " \
                                "where a.id = b.id and b.status = 'N' and c.status = 'N' and a.id = d.compid and c.id = d.appid " \
                                "and c.domainid in (WITH RECURSIVE rec (id) as ( SELECT a.id from dm.dm_domain a where id=" + str(domain) + " UNION ALL SELECT b.id from rec, dm.dm_domain b where b.domainid = rec.id ) SELECT * FROM rec) " \
                                "order by domainid, appid, compid"

                        df = pd.read_sql(sql, connection)
                        apptable =  df.pivot(index=["appid","compid", "domainid", "application", "component"], columns=['name'], values=['value']).reset_index()
                        apptable.columns = [ '_'.join(re.findall('.[^A-Z]*',re.sub(r'^value_','','_'.join(tup).rstrip('_')))) for tup in apptable.columns.values]

                        if 'license' not in apptable.columns:
                            apptable.insert(1, 'license', 'N')

                        if 'readme' not in apptable.columns:
                            apptable.insert(1, 'readme', 'N')

                        if 'swagger' not in apptable.columns:
                            apptable.insert(1, 'swagger', 'N')

                        if 'Git_Committers_Cnt' not in apptable.columns:
                            apptable.insert(1, 'Git_Committers_Cnt', 0)

                        if 'Git_Total_Committers_Cnt' not in apptable.columns:
                            apptable.insert(1, 'Git_Total_Committers_Cnt', 0)

                        if 'Job_Triggered_By' not in apptable.columns:
                            apptable.insert(1, 'Job_Triggered_By', '')

                        if 'Sonar_Bugs' not in apptable.columns:
                            apptable.insert(1, 'Sonar_Bugs', '')

                        if 'Sonar_Code_Smells' not in apptable.columns:
                            apptable.insert(1, 'Sonar_Code_Smells', '')

                        if 'Sonar_Violations' not in apptable.columns:
                            apptable.insert(1, 'Sonar_Violations', '')

                        if 'Sonar_Project_Status' not in apptable.columns:
                            apptable.insert(1, 'Sonar_Project_Status', '')

                        if 'Vericode_Score' not in apptable.columns:
                            apptable.insert(1, 'Vericode_Score', '')

                        if 'Git_Lines_Added' not in apptable.columns:
                            apptable.insert(1, 'Git_Lines_Added', 0)

                        if 'Git_Lines_Deleted' not in apptable.columns:
                            apptable.insert(1, 'Git_Lines_Deleted', 0)

                        if 'Git_Lines_Total' not in apptable.columns:
                            apptable.insert(1, 'Git_Lines_Total', 0)

                        if 'Lines_Changed' not in apptable.columns:
                            apptable.insert(1, 'Lines_Changed', 0)

                        apptable['Git_Lines_Added'] = pd.to_numeric(apptable['Git_Lines_Added'], errors='coerce').fillna(0).astype('int')
                        apptable['Git_Lines_Deleted'] = pd.to_numeric(apptable['Git_Lines_Deleted'], errors='coerce').fillna(0).astype('int')
                        apptable['Git_Lines_Total'] = pd.to_numeric(apptable['Git_Lines_Total'], errors='coerce').fillna(0).astype('int')

                        apptable['Lines_Changed'] = (apptable['Git_Lines_Added'] + apptable['Git_Lines_Deleted'])
                        apptable['Lines_Changed'] = apptable['Lines_Changed'].div(apptable['Git_Lines_Total']).replace(np.inf,0).round(2) * 100

                        apptable.drop('Git_Lines_Added', axis=1, inplace=True)
                        apptable.drop('Git_Lines_Deleted', axis=1, inplace=True)
                        apptable.drop('Git_Lines_Total', axis=1, inplace=True)

                        apptable['Git_Committers_Cnt'] = pd.to_numeric(apptable['Git_Committers_Cnt'], errors='coerce').fillna(0).astype('int')
                        apptable['Git_Total_Committers_Cnt'] = pd.to_numeric(apptable['Git_Total_Committers_Cnt'], errors='coerce').fillna(0).astype('int')

                        apptable['Contributing_Committers'] = apptable['Git_Committers_Cnt'].div(apptable['Git_Total_Committers_Cnt']).replace(np.inf,0).round(2) * 100

                        apptable.drop('Git_Committers_Cnt', axis=1, inplace=True)

                        apptable.set_index(['appid', 'compid'])

                        newcols = ["appid",
                                "compid",
                                "domainid",
                                "application",
                                "component",
                                "license",
                                "readme",
                                "swagger",
                                "Lines_Changed",
                                "Contributing_Committers",
                                "Git_Total_Committers_Cnt",
                                "Job_Triggered_By",
                                "Sonar_Bugs",
                                "Sonar_Code_Smells",
                                "Sonar_Violations",
                                "Sonar_Project_Status",
                                "Vericode_Score"]

                    #    set_dif = set(list(apptable.columns)).symmetric_difference(set(newcols))
                    #    temp3 = list(set_dif)
                    #    print(temp3)
                        apptable = apptable.reindex(columns=newcols)

                        table = pd.merge(apptable, envtable, how="left", on="appid")
                        table = table.fillna('')
                        table.rename(columns={'Job_Triggered_By': 'Git_Trigger'}, inplace=True)
                        table.rename(columns={'Git_Total_Committers_Cnt': 'Total_Committers'}, inplace=True)

                        cols = list(table.columns)
                        data.columns = []
                        for col in cols[3::]:
                            col = col.lower()
                            column = {"name": col, "data": col}
                            data.columns.append(column)

                        rows = []
                        # using a itertuples()
                        for i in table.itertuples():
                            row = i.Index
                            rowdict = {}

                            for col in cols[3::]:
                                val = getattr(i, col, None)
                                if (val is None):
                                    key = '_' + str(cols.index(col)-1)
                                    val = getattr(i, key, '')
                                if (col.startswith('Environment') and len(val.strip()) > 0):
                                    val = 'Y'
                                col = col.lower()
                                rowdict.update({col: val})
                            rows.append(rowdict)

                        data.data = rows
                        data.domain = domname
                        return data

            except (InterfaceError, OperationalError) as ex:
                if attempt < no_of_retry:
                    sleep_for = 0.2
                    logging.error(
                        "Database connection error: {} - sleeping for {}s"
                        " and will retry (attempt #{} of {})".format(
                            ex, sleep_for, attempt, no_of_retry
                        )
                    )
                    #200ms of sleep time in cons. retry calls
                    sleep(sleep_for)
                    attempt += 1
                    continue
                else:
                    raise

    except HTTPException:
        raise
    except Exception as err:
        print(str(err))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5010)


# Frequecy per week per env
# Time lag per env
# Lines changed between deploy per env ??
# Rollbacks per week per env ??
# Time to rollback ??
