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

# pylint: disable=E0401,E0611
# pyright: reportMissingImports=false,reportMissingModuleSource=false

import logging
import os
import re
import socket
from datetime import datetime
from time import sleep
from typing import Union

import numpy as np  # pylint: disable=E0401 # pyright: ignore[reportMissingImports]
import pandas as pd  # pylint: disable=E0401 # pyright: ignore[reportMissingImports]
import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel  # pylint: disable=E0611
from sqlalchemy import create_engine, sql
from sqlalchemy.exc import InterfaceError, OperationalError

tags_metadata = [
    {
        "name": "health",
        "description": "health check end point",
    }
]


def pad_number(match):
    number = int(match.group(1))
    return format(number, "03d")


def is_blank(mystr):
    return not (mystr and mystr.strip())


# Init Globals
SERVICE_NAME = "ortelius-ms-scorecard"
DB_CONN_RETRY = 3

app = FastAPI(title=SERVICE_NAME, description=SERVICE_NAME)

app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Init db connection
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "postgres")
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASS", "postgres")
db_port = os.getenv("DB_PORT", "5432")
validateuser_url = os.getenv("VALIDATEUSER_URL", "")

if len(validateuser_url) == 0:
    validateuser_host = os.getenv("MS_VALIDATE_USER_SERVICE_HOST", "127.0.0.1")
    host = socket.gethostbyaddr(validateuser_host)[0]
    validateuser_url = "http://" + host + ":" + str(os.getenv("MS_VALIDATE_USER_SERVICE_PORT", "80"))

engine = create_engine("postgresql+psycopg2://" + db_user + ":" + db_pass + "@" + db_host + ":" + db_port + "/" + db_name, pool_pre_ping=True)


# health check endpoint
class StatusMsg(BaseModel):
    status: str
    service_name: str


@app.get("/health", tags=["health"])
async def health(response: Response) -> StatusMsg:
    """
    This health check end point used by Kubernetes
    """
    try:
        with engine.connect() as connection:
            conn = connection.connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            if cursor.rowcount > 0:
                return StatusMsg(status="UP", service_name=SERVICE_NAME)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return StatusMsg(status="DOWN", service_name=SERVICE_NAME)

    except Exception as err:
        print(str(err))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return StatusMsg(status="DOWN", service_name=SERVICE_NAME)


# end health check

# validate user endpoint


class ScoreCard(BaseModel):
    domain: str = ""
    columns: list = []
    data: list = []


@app.get("/msapi/scorecard")
async def get_scorecard(  # noqa: C901
    frequency: Union[str, None] = None, environment: Union[str, None] = None, lag: Union[str, None] = None, appname: Union[str, None] = None, appid: Union[str, None] = None
) -> ScoreCard:
    domname = ""

    try:
        # Retry logic for failed query
        no_of_retry = DB_CONN_RETRY
        attempt = 1
        while True:
            try:
                with engine.connect() as connection:
                    conn = connection.connection
                    conn.cursor()

                    envorder = []
                    env_cursor = conn.cursor()
                    env_cursor.execute("SELECT envname from dm.dm_env_order order by id asc")
                    rows = env_cursor.fetchall()

                    for row in rows:
                        envorder.append(row[0])

                    if frequency is not None:
                        data = ScoreCard()

                        sqlstmt = (
                            "select application, environment, (monthly::date)::varchar as month, count(monthly) as frequency from dm.dm_app_scorecard "
                            "where application=:appname "
                            "group by application, month, environment "
                            "order by application, month desc, environment"
                        )
                        df = pd.read_sql(sql.text(sqlstmt), connection, params={"appname": appname})

                        if len(df.index) > 0:
                            table = df.pivot_table(values=["frequency"], index=["application", "environment", "month"], columns=["month"])

                            table = table.fillna(0)
                            cols = list(table.columns)

                            cols.insert(0, "Environment")
                            cols.insert(0, "Application")

                            appmap: dict[tuple, dict] = {}
                            rows = []
                            # using a itertuples()
                            for i in table.itertuples():
                                row = i.Index
                                application = row[0]
                                environment = row[1]

                                rowdict = {}
                                rowdict.update({cols[0]: row[0]})
                                rowdict.update({cols[1]: row[1]})
                                rowdict = appmap.get((application, environment), rowdict)

                                for col in cols[2::]:
                                    val = None
                                    if val is None:
                                        key = "_" + str(cols.index(col) - 1)
                                        val = getattr(i, key, 0)

                                    if rowdict.get(col[1], 0) == 0:
                                        rowdict.update({col[1]: val})
                                appmap.update({(application, environment): rowdict})

                            rows = list(appmap.values())

                            cols = []
                            if len(rows) > 0:
                                cols = list(rows[0].keys())
                                cols.remove("Application")
                                cols.remove("Environment")
                                cols.sort()

                            datarows = []
                            for row in rows:
                                newrow = []
                                newrow.append(row.get("Environment"))
                                for col in cols:
                                    newrow.append(row.get(col, 0))
                                datarows.append(newrow)

                            for index, item in enumerate(cols):
                                if "-" in item:
                                    dt = datetime.strptime(item, "%Y-%m-%d")
                                    cols[index] = dt.strftime("%b %Y")
                        else:
                            cols = ["Environment"]
                            datarows = []

                        data.columns = cols
                        data.data = datarows
                        return data
                    elif lag is not None:
                        data = ScoreCard()

                        cols = []

                        sqlstmt = (
                            "SELECT a.name AS application, "
                            "d.name AS environment, "
                            "b.deploymentid, "
                            "to_timestamp(a.created)::timestamp(0) as created, "
                            "b.startts::timestamp(0) as deployed "
                            "FROM dm_application a, "
                            "dm_deployment b, "
                            "dm_application c, "
                            "dm_environment d "
                            "WHERE a.id = b.appid AND b.envid = d.id "
                            "AND a.parentid = c.id AND c.name = :appname "
                            "AND deploymentid > 0 "
                            "UNION "
                            "SELECT a.name AS application, "
                            "d.name AS environment, "
                            "b.deploymentid, "
                            "to_timestamp(a.created)::timestamp(0) as created, "
                            "b.startts::timestamp(0) as deployed "
                            "FROM dm_application a, "
                            "dm_deployment b, "
                            "dm_application c, "
                            "dm_environment d "
                            "WHERE a.id = b.appid AND b.envid = d.id "
                            "AND a.parentid IS NULL AND a.name = :appname "
                            "AND deploymentid > 0 "
                            "order by application, environment, deploymentid "
                        )

                        df = pd.read_sql(sql.text(sqlstmt), connection, params={"appname": appname})

                        if len(df.index) > 0:
                            if not envorder:
                                envdf = df[["environment", "deploymentid"]].copy()
                                envdf = envdf.sort_values(by=["deploymentid", "environment"]).groupby(["environment"]).head(1)
                                envorder = envdf["environment"].to_list()

                            lagtab = df.sort_values(by=["application", "environment", "deploymentid"], ascending=[True, True, False]).groupby(["application", "environment"]).head(1)
                            lagtab.assign(**lagtab[["created", "deployed"]].apply(pd.to_datetime, format="%Y-%m-%d %H:%M:%S"), inplace=True)
                            lagtab["diff"] = round((lagtab.deployed - lagtab.created).fillna(pd.Timedelta(seconds=0)).dt.total_seconds() / 86400.0, 2)
                            lagtab.drop("deploymentid", axis=1, inplace=True)
                            lagtab.drop("created", axis=1, inplace=True)
                            lagtab.drop("deployed", axis=1, inplace=True)
                            table = lagtab.pivot_table(values=["diff"], index=["application"], columns=["environment"]).reset_index()
                            table.fillna(0, inplace=True)

                            cols = list(table.columns)
                            newcols = ["Application"]
                            for col in cols:
                                if col[0] == "diff":
                                    newcols.append(col[1])

                            sortedcols = ["Application"]
                            for item in envorder:
                                if item in newcols:
                                    sortedcols.append(item)
                            table.columns = sortedcols

                            datarows = []
                            # using a itertuples()
                            for row in table.itertuples():
                                outrow = []

                                for k in range(1, len(row)):
                                    outrow.append(row[k])

                                if sum(outrow[1:]) > 0:
                                    datarows.append(outrow)
                            cols = list(table.columns)[1:]
                        else:
                            cols = ["Application"]
                            datarows = []

                        data.columns = cols
                        data.data = datarows

                        return data
                    else:
                        data = ScoreCard()
                        # Read data from PostgreSQL database table and load into a DataFrame instance
                        sqlstmt = """
                            select distinct a.id as appid, b.name as environment
                            from dm.dm_application a, dm.dm_environment b, dm.dm_deployment c where a.id = c.appid and c.envid = b.id order by 1, 2
                        """

                        df = pd.read_sql(sql.text(sqlstmt), connection)
                        envtable = df.pivot(index="appid", columns="environment", values="environment")

                        cols = list(envtable.columns)
                        newcols = []
                        for envname in envorder:
                            if envname in cols:
                                newcols.append(envname)
                        missingcols = list(set(cols).difference(set(newcols)))
                        newcols.extend(missingcols)
                        envtable = envtable.reindex(columns=newcols)

                        cols = []
                        for col in list(envtable.columns):
                            cols.append("Env:_" + col)
                        envtable.columns = cols

                        sqlstmt = """
                            select distinct c.domainid, c.id as appid, b.id as compid, c.name as application, b.name as component, a.name as name, a.value as value
                            from dm.dm_scorecard_nv a, dm.dm_component b, dm.dm_application c, dm.dm_applicationcomponent d
                            where a.id = b.id and b.status = 'N' and c.status = 'N' and a.id = d.compid and c.id = d.appid and
                            (c.id = :appid or c.parentid in (select parentid from dm.dm_application where id = :appid))
                        """

                        df = pd.read_sql(sql.text(sqlstmt), connection, params={"appid": appid})

                        apptable = df.pivot(index=["appid", "compid", "domainid", "application", "component"], columns=["name"], values=["value"]).reset_index()
                        apptable.columns = ["_".join(re.findall(".[^A-Z]*", re.sub(r"^value_", "", "_".join(tup).rstrip("_")))) for tup in apptable.columns.values]

                        if "license" not in apptable.columns:
                            apptable.insert(1, "license", "N")

                        if "readme" not in apptable.columns:
                            apptable.insert(1, "readme", "N")

                        if "swagger" not in apptable.columns:
                            apptable.insert(1, "swagger", "N")

                        if "Git_Committers_Cnt" not in apptable.columns:
                            apptable.insert(1, "Git_Committers_Cnt", 0)

                        if "Git_Total_Committers_Cnt" not in apptable.columns:
                            apptable.insert(1, "Git_Total_Committers_Cnt", 0)

                        if "Job_Triggered_By" not in apptable.columns:
                            apptable.insert(1, "Job_Triggered_By", "")

                        if "Sonar_Bugs" not in apptable.columns:
                            apptable.insert(1, "Sonar_Bugs", "")

                        if "Sonar_Code_Smells" not in apptable.columns:
                            apptable.insert(1, "Sonar_Code_Smells", "")

                        if "Sonar_Violations" not in apptable.columns:
                            apptable.insert(1, "Sonar_Violations", "")

                        if "Sonar_Project_Status" not in apptable.columns:
                            apptable.insert(1, "Sonar_Project_Status", "")

                        if "Veracode_Score" not in apptable.columns:
                            apptable.insert(1, "Veracode_Score", "")

                        if "Git_Lines_Added" not in apptable.columns:
                            apptable.insert(1, "Git_Lines_Added", 0)

                        if "Git_Lines_Deleted" not in apptable.columns:
                            apptable.insert(1, "Git_Lines_Deleted", 0)

                        if "Git_Lines_Total" not in apptable.columns:
                            apptable.insert(1, "Git_Lines_Total", 0)

                        if "Lines_Changed" not in apptable.columns:
                            apptable.insert(1, "Lines_Changed", 0)

                        apptable["Git_Lines_Added"] = pd.to_numeric(apptable["Git_Lines_Added"], errors="coerce").fillna(0).astype("int")
                        apptable["Git_Lines_Deleted"] = pd.to_numeric(apptable["Git_Lines_Deleted"], errors="coerce").fillna(0).astype("int")
                        apptable["Git_Lines_Total"] = pd.to_numeric(apptable["Git_Lines_Total"], errors="coerce").fillna(0).astype("int")

                        apptable["Lines_Changed"] = apptable["Git_Lines_Added"] + apptable["Git_Lines_Deleted"]
                        apptable["Lines_Changed"] = apptable["Lines_Changed"].div(apptable["Git_Lines_Total"]).replace(np.inf, 0).round(2) * 100

                        apptable.drop("Git_Lines_Added", axis=1, inplace=True)
                        apptable.drop("Git_Lines_Deleted", axis=1, inplace=True)
                        apptable.drop("Git_Lines_Total", axis=1, inplace=True)

                        apptable["Git_Committers_Cnt"] = pd.to_numeric(apptable["Git_Committers_Cnt"], errors="coerce").fillna(0).astype("int")
                        apptable["Git_Total_Committers_Cnt"] = pd.to_numeric(apptable["Git_Total_Committers_Cnt"], errors="coerce").fillna(0).astype("int")

                        apptable["Contributing_Committers"] = apptable["Git_Committers_Cnt"].div(apptable["Git_Total_Committers_Cnt"]).replace(np.inf, 0).round(2) * 100

                        apptable.drop("Git_Committers_Cnt", axis=1, inplace=True)

                        apptable.set_index(["appid", "compid"])

                        apptable.Job_Triggered_By = apptable.Job_Triggered_By.apply(lambda x: "Y" if "SCM" in str(x) else "N")

                        apptable["appver"] = apptable.application.apply(lambda x: re.sub(r"(\d+)", pad_number, x))
                        apptable.sort_values(by=["appver", "component"], ascending=[False, False], inplace=True)
                        apptable.drop("appver", axis=1, inplace=True)

                        apptable = apptable.reindex(
                            columns=[
                                "appid",
                                "compid",
                                "domainid",
                                "application",
                                "component",
                                "Sonar_Bugs",
                                "Sonar_Code_Smells",
                                "Sonar_Violations",
                                "Sonar_Project_Status",
                                "Veracode_Score",
                                "Job_Triggered_By",
                                "Contributing_Committers",
                                "Git_Total_Committers_Cnt",
                                "Lines_Changed",
                                "swagger",
                                "readme",
                                "license",
                            ]
                        )

                        table = pd.merge(apptable, envtable, how="left", on="appid")
                        table = table.fillna("")
                        table.rename(columns={"Job_Triggered_By": "Git_Trigger"}, inplace=True)
                        table.rename(columns={"Git_Total_Committers_Cnt": "Total_Committers"}, inplace=True)

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
                                val = None
                                if col:
                                    val = getattr(i, col, None)
                                if val is None:
                                    key = "_" + str(cols.index(col) - 1)
                                    val = getattr(i, key, "")

                                valstr = ""
                                if val is not None:
                                    valstr = str(val)

                                if col.startswith("Env:") and len(valstr.strip()) > 0:
                                    val = "Y"
                                col = col.lower()
                                rowdict.update({col: val})
                            rows.append(rowdict)

                        data.data = rows
                        data.domain = domname
                        return data

            except (InterfaceError, OperationalError) as ex:
                if attempt < no_of_retry:
                    sleep_for = 0.2
                    logging.error("Database connection error: %s - sleeping for %d seconds and will retry (attempt #%d of %d)", ex, sleep_for, attempt, no_of_retry)
                    # 200ms of sleep time in cons. retry calls
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
    uvicorn.run(app, port=5010)

# Frequecy per month per env
# Time lag per env
# Lines changed between deploy per env ??
# Rollbacks per month per env ??
# Time to rollback ??
