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
import socket
from time import sleep
from typing import Optional, Union

import psycopg2.extras
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.exc import InterfaceError, OperationalError


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


@app.get("/health",
         responses={
             503: {"model": StatusMsg,
                   "description": "DOWN Status for the Service",
                   "content": {
                       "application/json": {
                           "example": {"status": 'DOWN'}
                       },
                   },
                   },
             200: {"model": StatusMsg,
                   "description": "UP Status for the Service",
                   "content": {
                       "application/json": {
                           "example": {"status": 'UP', "service_name": service_name}
                       }
                   },
                   },
         }
         )
async def health(response: Response):
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
class Message(BaseModel):
    detail: str

@app.get('/msapi/scorecard',
         responses={
             401: {"model": Message,
                   "description": "Authorization Status",
                   "content": {
                       "application/json": {
                           "example": {"detail": "Authorization failed"}
                       },
                   },
                   },
             500: {"model": Message,
                   "description": "SQL Error",
                   "content": {
                       "application/json": {
                           "example": {"detail": "SQL Error: 30x"}
                       },
                   },
                   },
             200: {
                 "model": ScoreCard,
                 "description": "Component Paackage Dependencies"},
             "content": {
                 "application/json": {
                     "example": {"data": [{"packagename": "Flask", "packageversion": "1.2.2", "name": "BSD-3-Clause", "url": "https://spdx.org/licenses/BSD-3-Clause.html", "summary": ""}]}
                 }
             }
         }
         )
async def getScoreCard(request: Request, domain: Union[str, None] = None, env: Union[str, None] = None):

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

                    sql = "SELECT * from dm.dm_scorecard_ui"

                    if (domain is not None):
                        cursor2 = conn.cursor()
                        cursor2.execute('SELECT fulldomain(' + str(domain) + ')')
                        if cursor2.rowcount > 0:
                            row = cursor2.fetchone()
                            domname = row[0]
                        cursor2.close()
                        
                        sql = sql + " where domain in (WITH RECURSIVE rec (id) as ( SELECT a.id from dm.dm_domain a where id=" + str(domain) + " UNION ALL SELECT b.id from rec, dm.dm_domain b where b.domainid = rec.id ) SELECT * FROM rec);"

                    cursor.execute(sql)

                    data = ScoreCard()
                    data.domain = domname

                    data.columns = []
                    for col in cursor.description:
                        column = {"name": col[0], "data": col[0]}
                        if (col[0] != 'domain'):
                            data.columns.append(column)

                    row = cursor.fetchone()
                    rows = []
                    while row:
                        rowdict = {}
                        i = 1
                        for col in data.columns:
                            name = col.get('name')
                            value = row[i]
                            rowdict.update({name: value})
                            i = i + 1
                        rows.append(rowdict)
                        row = cursor.fetchone() 
                    data.data = rows
                    cursor.close()
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
