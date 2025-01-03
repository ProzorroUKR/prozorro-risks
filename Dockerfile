FROM python:3.10-alpine3.19 as base

RUN pip install --upgrade pip
RUN addgroup -g 10000 user && \
    adduser -S -u 10000 -G user -h /app user

WORKDIR /app
RUN apk --no-cache add gcc build-base git openssl-dev libffi-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY swagger /swagger
EXPOSE 8080

FROM base as test_base

COPY tests/requirements.txt ./test-requirements.txt
COPY .flake8 /.flake8
RUN pip install --no-cache-dir -r test-requirements.txt

FROM base as prod

ADD src/ .
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

FROM test_base as test

ADD src/ .
ADD tests/ tests/
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

FROM prod as local

FROM prod

RUN chown -R user:user /app
USER user
