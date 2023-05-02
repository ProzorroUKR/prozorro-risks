# Prozorro Risks API

## System requirements

* make
* docker
* docker-compose

# Usage

### Run

To start the project in development mode, run the following command:

```
make run
```

or just

```
make start
```

To stop docker containers:

```
make stop
```

To clean up docker containers (removes containers, networks, volumes, and images created by docker-compose up):

```
make remove-compose
```

or just

```
make clean
```

Shell inside the running container

```
make bash # the command can be executed only if the server is running e.g. after `make run`
```

### Linters

To run flake8:

```
make lint
```

All the settings for `flake8` can be customized in `.flake8` file


### Env variables

There are few env variables that can be configured in docker-compose.yaml for local deployment:

* PUBLIC_API_HOST - link for tenders' and contracts' API host
(e.g. 'https://api.prozorro.gov.ua')

* FORWARD_CHANGES_COOLDOWN_SECONDS - time for crawler sleeping. It may be needed for optimizing tender processing. Tenders may be modified too often, for instance every 5 minutes. This configuration allows crawler to wait and not process too fresh tenders that might be modified in the nearest future one more time. This configuration is in seconds. 

E.g. to let crawler sleep for 10 hours and then process all tenders that had been modifying during this time:
```
FORWARD_CHANGES_COOLDOWN_SECONDS: '36000'
```
Or you can set FORWARD_CHANGES_COOLDOWN_SECONDS: '' for crawler not to sleep.

* FORWARD_OFFSET - timestamp from what period of time crawler starts processing tenders. 
E.g. 
```
FORWARD_OFFSET: '1672524000.0'  # 2023-01-01T00:00:00+02:00
```