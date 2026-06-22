FROM python:3.13-alpine AS base

RUN apk --no-cache add gcc build-base git openssl-dev libffi-dev

RUN addgroup -g 10000 user && \
    adduser -S -u 10000 -G user -h /app user

# Set app home
ENV APP_HOME=/app
WORKDIR ${APP_HOME}

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

# Set the virtualenv
ENV VIRTUAL_ENV=${APP_HOME}/.venv
ENV PATH=${APP_HOME}/.venv/bin:$PATH
ENV PATH=${APP_HOME}:$PATH

# Dependency manifests (synced per target below)
COPY pyproject.toml uv.lock ${APP_HOME}/

COPY swagger /swagger
ENV SWAGGER_DOC_PATH=/swagger
EXPOSE 8080

FROM base AS test

# Install dependencies including the dev group (pytest, flake8, ...)
RUN uv sync --frozen --no-cache --compile-bytecode

COPY .flake8 /.flake8
ADD src/ .
ADD tests/ tests/
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

FROM base AS prod

# Install runtime dependencies only
RUN uv sync --frozen --no-cache --no-dev --compile-bytecode

ADD src/ .
ARG version=unknown
RUN echo $version && sed -i "s/##VERSION##/$version/g" prozorro/__init__.py

RUN chown -R user:user ${APP_HOME}
USER user
