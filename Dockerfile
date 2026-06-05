FROM python:3.10-alpine3.19 AS base

RUN pip install --upgrade pip
RUN addgroup -g 10000 user && \
    adduser -S -u 10000 -G user -h /app user

WORKDIR /app
RUN apk --no-cache add gcc build-base git openssl-dev libffi-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY swagger /swagger
ENV SWAGGER_DOC_PATH=/swagger
EXPOSE 8080

FROM base AS test_base

COPY tests/requirements.txt ./test-requirements.txt
COPY .flake8 /.flake8
RUN pip install --no-cache-dir -r test-requirements.txt

FROM base AS prod

ADD src/ .
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

FROM test_base AS test

ADD src/ .
ADD tests/ tests/
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

FROM prod AS local

FROM prod

RUN chown -R user:user /app
USER user
