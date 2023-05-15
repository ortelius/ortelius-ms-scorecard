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
FROM alpine:edge

WORKDIR /app
COPY . /app

ENV PYTHONPATH=/usr/lib/python3.11/site-packages
RUN apk --no-cache add libbz2=1.0.8-r6 py3-numpy=1.24.3-r0 py3-pandas=1.5.3-r1 python3=3.11.3-r11; \
    apk upgrade

RUN python -m ensurepip --default-pip; \
    pip install --no-cache-dir -r requirements.txt; \
    cp "$(which uvicorn)" /app; \
    pip uninstall -y pip wheel setuptools

ENV DB_HOST localhost
ENV DB_NAME postgres
ENV DB_USER postgres
ENV DB_PASS postgres
ENV DB_PORT 5432

EXPOSE 8080

ENTRYPOINT ["/app/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
