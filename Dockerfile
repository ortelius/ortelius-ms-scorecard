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
FROM python:3.11.2-alpine3.17

WORKDIR /app
COPY . /app

ENV PYTHONPATH=/usr/lib/python3.11/site-packages
RUN apk --no-cache add libbz2;
RUN apk add py3-numpy py3-pandas --repository=https://dl-cdn.alpinelinux.org/alpine/edge/community;

RUN pip install --upgrade pip; \
    pip install --no-cache-dir -r requirements.txt; \
    cp $(which uvicorn) /app; \
    pip uninstall -y pip wheel setuptools

ENV DB_HOST localhost
ENV DB_NAME postgres
ENV DB_USER postgres
ENV DB_PASS postgres
ENV DB_PORT 5432

EXPOSE 8080

ENTRYPOINT ["/app/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
