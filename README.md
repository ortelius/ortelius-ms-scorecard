# ortelius-ms-dep-pkg-r
Dependency Package Data Microservice - Read

This is a flask web application which returns a list of objects known as Component Dependencies when the 
endpoint `/msapi/deppkg` is accessed. 

# Setup
- Clone the repository on your local computer

### Start Postgres
The project requires a Postgres server to be running. This can be done by either installing Postgres directly on 
your machine and making available the following environmental variables for your python application:

| Environmental Variable | Description |
| --------- | --------- |
| DB_NAME | The name of the database you have created for the purpose of this project |
| DB_HOST | The host name of the database server |
| DB_USER | The username that would be used to access the database |
| DB_PASSWORD | The password to the database attached to the provided above user |
| DB_PORT | The port that the postgres server run on. Usually 5432. |

You can make these environmental variables by creating a `.env` file (will be ignored by git) in the 
project root and filling with the required environmental variables like as shown below (these are 
injected into the docker container at runtime):

```text
DB_HOST=localhost
DB_NAME=db
DB_PASSWORD=password
DB_USER=user
DB_PORT=5433
```

### To start the flask application
The flask application has been dockerized and can be utilized by following the steps below;
- Build the docker image using the following command
  ```shell
  docker build -t comp-dep .
  ```
- Run the docker on local machine by executing the following command 
  ```shell
  docker run -p 5000:5000 --env-file .env -d comp-dep
  ```
- You should be able to access the webpage at [localhost:5000](http://www.localhost:5000/) and the list of 
component dependencies in json at [http://localhost:5000/msapi/deppkg](http://localhost:5000/msapi/deppkg)

------------------------------------------

Another option is to make use of [Docker compose](https://docs.docker.com/compose/) to start up the project 
at once. You can simply run:

```shell
docker-compose up --build
```

This command starts up the database server, the flask application and seeds the database with dummy data.
Once you do this, you should be able to access the webpage at [localhost:5000](http://www.localhost:5000/).
And hitting [http://localhost:5000/msapi/deppkg](http://localhost:5000/msapi/deppkg) should return a response like this:

```json
[
    {
        "compid": 1,
        "packagename": "Package 1",
        "packageversion": "0.1",
        "cve": "CVE 1",
        "cve_url": "https://google.com/search?q=1",
        "license": "License 1",
        "license_url": "https://google.com/search?q=1"
    },
    {
        "compid": 2,
        "packagename": "Package 2",
        "packageversion": "0.2",
        "cve": "CVE 2",
        "cve_url": "https://google.com/search?q=2",
        "license": "License 2",
        "license_url": "https://google.com/search?q=2"
    },
    {
        "compid": 3,
        "packagename": "Package 3",
        "packageversion": "0.3",
        "cve": "CVE 3",
        "cve_url": "https://google.com/search?q=3",
        "license": "License 3",
        "license_url": "https://google.com/search?q=3"
    },
    {
        "compid": 4,
        "packagename": "Package 4",
        "packageversion": "0.4",
        "cve": "CVE 4",
        "cve_url": "https://google.com/search?q=4",
        "license": "License 4",
        "license_url": "https://google.com/search?q=4"
    }
]
```