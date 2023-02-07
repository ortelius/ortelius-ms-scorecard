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
FROM python:3.10-slim AS build-env

### Install pipenv and compilation dependencies
RUN apt-get update; \
    apt-get install -y --no-install-recommends gcc libbz2-dev;

COPY . /app
WORKDIR /app

RUN pip install --upgrade pip; \
    pip install --no-cache-dir --upgrade -r requirements.txt; \
    pip uninstall -y pip wheel setuptools; \
    cp $(which uvicorn) /app

# Runtime
FROM al3xos/python-distroless:3.10-debian11

ENV DB_HOST localhost
ENV DB_NAME postgres
ENV DB_USER postgres
ENV DB_PASS postgres
ENV DB_PORT 5432

COPY --from=build-env /app /app
COPY --from=build-env /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=build-env /usr/lib/x86_64-linux-gnu/libsqlite3* /usr/lib/x86_64-linux-gnu
COPY --from=build-env /lib/x86_64-linux-gnu/libbz2* /lib/x86_64-linux-gnu
ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages

WORKDIR /app

EXPOSE 80
ENTRYPOINT ["./uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
