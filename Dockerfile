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
FROM alpine:edge@sha256:d81baec21ea8f039866c659d5633b77b0138faa9d4aaee26151dd03c65e09d27

WORKDIR /app
COPY . /app

ENV PIP_BREAK_SYSTEM_PACKAGES 1
ENV PYTHONPATH=/usr/lib/python3.11/site-packages
RUN apk update; \
    apk add --no-cache python3; \
    apk upgrade

RUN rm /usr/lib/python3.11/EXTERNALLY-MANAGED; \
    python -m ensurepip --default-pip; \
    pip install --no-cache-dir pip==23.3.1; \
    pip install --no-cache-dir -r requirements.in --no-warn-script-location; \
    cp "$(which uvicorn)" /app; \
    pip uninstall -y pip wheel setuptools

ENV DB_HOST localhost
ENV DB_NAME postgres
ENV DB_USER postgres
ENV DB_PASS postgres
ENV DB_PORT 5432

EXPOSE 8080

ENTRYPOINT ["/app/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
