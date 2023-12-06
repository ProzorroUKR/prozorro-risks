from aiohttp import web
from aiohttp_swagger import setup_swagger
from prozorro import version
from prozorro.risks.middleware import (
    cors_middleware,
    request_id_middleware,
    request_unpack_params,
    convert_response_to_json,
)
from prozorro.risks.db import init_mongodb, cleanup_db_client
from prozorro.risks.logging import AccessLogger, setup_logging
from prozorro.risks.handlers import (
    download_risks_report,
    get_filter_values,
    get_tender_risks,
    get_version,
    list_tenders,
    ping_handler,
    get_tenders_feed,
)
from prozorro.risks.settings import CLIENT_MAX_SIZE, SENTRY_DSN, SWAGGER_DOC_AVAILABLE
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
import sentry_sdk
import logging

logger = logging.getLogger(__name__)


def create_application(on_cleanup=None):
    app = web.Application(
        middlewares=(
            cors_middleware,
            request_id_middleware,
            convert_response_to_json,
            request_unpack_params,
        ),
        client_max_size=CLIENT_MAX_SIZE,
    )
    app.router.add_get("/api/ping", ping_handler, allow_head=False)
    app.router.add_get("/api/version", get_version, allow_head=False)
    app.router.add_get(r"/api/risks/{tender_id:[\w-]+}", get_tender_risks, allow_head=False)
    app.router.add_get("/api/risks", list_tenders, allow_head=False)
    app.router.add_get("/api/filter-values", get_filter_values, allow_head=False)
    app.router.add_get("/api/risks-report", download_risks_report, allow_head=False)
    app.router.add_get("/api/risks-feed", get_tenders_feed, allow_head=False)

    app.on_startup.append(init_mongodb)
    if on_cleanup:
        app.on_cleanup.append(on_cleanup)
    app.on_cleanup.append(cleanup_db_client)
    return app


if __name__ == "__main__":
    setup_logging()
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN, integrations=[AioHttpIntegration()])
    logger.info("Starting app on 0.0.0.0:8080")

    application = create_application()

    if SWAGGER_DOC_AVAILABLE:
        setup_swagger(
            application,
            title="Prozorro Risks API",
            description="Prozorro Risks description",
            api_version=version,
            ui_version=3,
        )
    web.run_app(
        application,
        host="0.0.0.0",
        port=8080,
        access_log_class=AccessLogger,
        print=None,
    )
