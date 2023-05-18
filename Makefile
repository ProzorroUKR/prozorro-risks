PROJECT_NAME=risks
IMAGE ?= prozorro-$(PROJECT_NAME):develop
IMAGE_TEST ?= prozorro-$(PROJECT_NAME):develop-test
IMAGE_FRONTEND ?= prozorro-$(PROJECT_NAME)-frontend:develop
CI_COMMIT_SHORT_SHA ?= $(shell git rev-parse --short HEAD)
GIT_STAMP ?= $(shell git describe || echo v0.1.0)
COMPOSE_PROJECT_NAME ?= $(PROJECT_NAME)-$(CI_PIPELINE_ID)
GIT_TAG ?= $(shell git describe --abbrev=0)

ifdef CI
  REBUILD_IMAGES_FOR_TESTS =
  NODE_ENV = production
else
  REBUILD_IMAGES_FOR_TESTS = docker-build
  NODE_ENV = development
endif

.EXPORT_ALL_VARIABLES:

# Common

start: run
clean: remove-compose

## Runs application development on docker. Builds, creates, starts containers for a service. | Common
run: docker-build
	@docker-compose up $(PROJECT_NAME) frontend

## Stops application. Stops running container without removing them.
stop:
	@docker-compose stop

## Show logs
logs:
	@docker-compose logs -f $(PROJECT_NAME)

## Stop application and remove containers for a service.
remove-compose:
	@docker-compose down -v
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-integration down -v
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-unit down -v
	@docker-compose rm -fsv
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-integration rm -fsv
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-unit rm -fsv
	@docker network ls -q -f name=$(COMPOSE_PROJECT_NAME)* | xargs --no-run-if-empty docker network rm

## Runs command `bash` commands in docker container.
bash:
	@docker exec -it $(PROJECT_NAME) bash

## Builds docker image
docker-build:
	@docker build $(IMAGE_TARGET) --build-arg version=$(GIT_STAMP) \
 								  --build-arg NODE_ENV=$(NODE_ENV) -t $(IMAGE) .
	@docker build --target=test --build-arg version=$(GIT_STAMP)  \
								--build-arg NODE_ENV=development -t $(IMAGE_TEST) .
	@docker build -t ${IMAGE_FRONTEND} . -f frontend/Dockerfile

## Runs integration tests | Tests
test-integration: $(REBUILD_IMAGES_FOR_TESTS)
	@docker rm -f $(PROJECT_NAME)-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID) || true
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-integration \
 	run --name $(PROJECT_NAME)-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID) \
    $(PROJECT_NAME)-test-integration pytest -v -q --cov-report= --cov=prozorro/risks tests/integration/
	@docker cp $(PROJECT_NAME)-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID):/app/.coverage .coverage.integration

## Runs unit tests
test-unit: $(REBUILD_IMAGES_FOR_TESTS)
	@docker rm -f $(PROJECT_NAME)-unit-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID) || true
	@docker-compose -p $(COMPOSE_PROJECT_NAME)-unit \
	run --name $(PROJECT_NAME)-unit-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID) \
	$(PROJECT_NAME)-test-unit pytest -v -q --cov-report= --cov=prozorro/risks tests/unit/
	@docker cp $(PROJECT_NAME)-unit-$(CI_COMMIT_SHORT_SHA)$(CI_PIPELINE_ID):/app/.coverage .coverage.unit

## Formats code with `flake8`.
lint: docker-build
	@docker-compose run --rm $(PROJECT_NAME)-test-integration sh -c "pip install flake8 && flake8 prozorro/"

## Create tag | Release
version:
	$(eval VERSION ?= $(shell read -p "Version: " VERSION; echo $$VERSION))
	echo "Tagged release $(VERSION)\n" > Changelog-$(VERSION).txt
	git log --oneline --no-decorate --no-merges $(GIT_TAG)..HEAD >> Changelog-$(VERSION).txt
	git tag -a -e -F Changelog-$(VERSION).txt $(VERSION)
