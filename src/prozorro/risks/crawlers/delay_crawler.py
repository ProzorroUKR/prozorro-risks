from datetime import datetime

from prozorro_crawler.main import main
from prozorro.risks.crawlers.tenders_crawler import fetch_and_process_tender
from prozorro.risks.db import init_mongodb
from prozorro.risks.logging import setup_logging
from prozorro.risks.rules.sas24_3_1 import RiskRule as RiskRuleSas24_3_1
from prozorro.risks.settings import SENTRY_DSN
from prozorro.risks.utils import get_now
import asyncio
import logging
import sentry_sdk


logger = logging.getLogger(__name__)

RISK_RULES = [RiskRuleSas24_3_1]
TENDER_RISKS = []
for risk_name in RISK_RULES:
    risk_rule = risk_name()
    if risk_rule.end_date and get_now().date() >= datetime.strptime(risk_rule.end_date, "%Y-%m-%d").date():
        continue
    if hasattr(risk_rule, "process_tender"):
        TENDER_RISKS.append(risk_rule)
print(TENDER_RISKS)


async def risks_data_handler(session, items):
    process_items_tasks = []
    for item in items:
        coroutine = fetch_and_process_tender(session, item["id"], tender_risks=TENDER_RISKS)
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    setup_logging()
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN)
    logger.info("Delay crawler started")
    main(risks_data_handler, init_task=init_mongodb)
