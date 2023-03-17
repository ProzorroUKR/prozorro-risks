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
