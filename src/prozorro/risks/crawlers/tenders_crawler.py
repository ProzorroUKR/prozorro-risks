import sys
from datetime import datetime

from prozorro_crawler.main import main
from prozorro.risks.crawlers.base import process_risks
from prozorro.risks.db import init_mongodb, save_tender, update_tender_risks
from prozorro.risks.logging import setup_logging
from prozorro.risks.requests import get_object_data
from prozorro.risks.settings import CRAWLER_START_DATE, SENTRY_DSN
from prozorro.risks.utils import get_now, tender_should_be_checked_for_termination, get_subject_of_procurement
from prozorro.risks.rules import *  # noqa
import asyncio
import logging
import sentry_sdk


logger = logging.getLogger(__name__)

RISK_RULES_MODULE = "prozorro.risks.rules"
RISK_MODULES = sys.modules[RISK_RULES_MODULE].__all__
TENDER_RISKS = []
for module_name in RISK_MODULES:
    risk_module = getattr(sys.modules[RISK_RULES_MODULE], module_name)
    risk_rule = getattr(risk_module, "RiskRule")()
    if risk_rule.end_date and get_now().date() >= datetime.strptime(risk_rule.end_date, "%Y-%m-%d").date():
        continue
    if hasattr(risk_rule, "process_tender"):
        TENDER_RISKS.append(risk_rule)


async def process_tender(tender, tender_risks=TENDER_RISKS):
    """
    Process tender with provided risk rules and save processed results to database.
    Also save tender to tenders mongo collection for calculating historical data.

    :param tender: dict Tender data
    :param tender_risks: list of risk rules
    """
    identifier = tender.get("procuringEntity", {}).get("identifier", {})
    tender["procuringEntityIdentifier"] = f'{identifier.get("scheme", "")}-{identifier.get("id", "")}'
    tender["subjectOfProcurement"] = get_subject_of_procurement(tender)

    risks = await process_risks(tender, tender_risks)
    if risks or tender_should_be_checked_for_termination(tender):
        tender_data = {
            "dateCreated": tender.get("dateCreated"),
            "dateModified": tender.get("dateModified"),
            "value": tender.get("value"),
            "procuringEntity": tender.get("procuringEntity"),
            "procuringEntityRegion": tender.get("procuringEntity", {}).get("address", {}).get("region", ""),
            "procuringEntityEDRPOU": tender.get("procuringEntity", {}).get("identifier", {}).get("id", ""),
            "tenderID": tender.get("tenderID"),
            "status": tender.get("status"),
        }
        if risks:
            tender_data["dateAssessed"] = get_now().isoformat()
        await update_tender_risks(
            tender["id"],
            risks,
            tender_data,
            contracts=tender["contracts"] if tender.get("contracts") else None,
        )

    # for some risk rules it is required to have saved tenders in database for processing statistics
    await save_tender(tender)


async def fetch_and_process_tender(session, tender_id, tender_risks=TENDER_RISKS):
    """
    Fetch more detailed information about tender and process tender whether it has risks.
    Crawler offset is watching dateModified field that's why here is validation
    whether tender dateCreated is more than or equal CRAWLER_START_DATE, just to filter out old tenders.

    :param session: ClientSession
    :param tender_id: str Id of particular tender
    :param tender_risks: list of risk rules
    """
    tender = await get_object_data(session, tender_id)
    if datetime.fromisoformat(tender["dateCreated"]) >= CRAWLER_START_DATE:
        await process_tender(tender, tender_risks=tender_risks)


async def risks_data_handler(session, items):
    process_items_tasks = []
    for item in items:
        coroutine = fetch_and_process_tender(session, item["id"])
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    setup_logging()
    if SENTRY_DSN:
        sentry_sdk.init(dsn=SENTRY_DSN)
    logger.info("Tender crawler started")
    main(risks_data_handler, init_task=init_mongodb)
