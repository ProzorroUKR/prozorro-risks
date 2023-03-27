import sys
from datetime import datetime

from prozorro_crawler.main import main
from prozorro.risks.db import init_mongodb, save_tender, update_tender_risks
from prozorro.risks.logging import setup_logging
from prozorro.risks.requests import get_object_data
from prozorro.risks.settings import CRAWLER_START_DATE
from prozorro.risks.utils import get_now, process_risks
from prozorro.risks.rules import *  # noqa
import asyncio
import logging


logger = logging.getLogger(__name__)

RISK_RULES_MODULE = "prozorro.risks.rules"
RISK_MODULES = sys.modules[RISK_RULES_MODULE].__all__
TENDER_RISKS = []
for module_name in RISK_MODULES:
    risk_module = getattr(sys.modules[RISK_RULES_MODULE], module_name)
    risk_rule = getattr(risk_module, "RiskRule")()
    if hasattr(risk_rule, "process_tender"):
        TENDER_RISKS.append(risk_rule)


async def process_tender(tender):
    """
    Process tender with provided risk rules and save processed results to database.
    Also save tender to tenders mongo collection for calculating historical data.

    :param tender: dict Tender data
    """
    uid = tender.pop("id" if "id" in tender else "_id")
    identifier = tender.get("procuringEntity", {}).get("identifier", {})
    tender["procuringEntityIdentifier"] = f'{identifier.get("scheme", "")}-{identifier.get("id", "")}'

    # for some risk rules it is required to have saved tenders in database for processing statistics
    await save_tender(uid, tender)

    worked_risks, risks = await process_risks(tender, TENDER_RISKS)
    if risks:
        await update_tender_risks(
            uid,
            worked_risks,
            risks,
            {
                "dateModified": tender.get("dateModified"),
                "dateAssessed": get_now().isoformat(),
                "value": tender.get("value"),
                "procuringEntity": tender.get("procuringEntity"),
                "procuringEntityRegion": tender.get("procuringEntity", {}).get("address", {}).get("region", "").lower(),
                "procuringEntityEDRPOU": tender.get("procuringEntity", {}).get("identifier", {}).get("id", ""),
            },
        )


async def fetch_and_process_tender(session, tender_id):
    """
    Fetch more detailed information about tender and process tender whether it has risks.
    Crawler offset is watching dateModified field that's why here is validation
    whether tender dateCreated is more than or equal CRAWLER_START_DATE, just to filter out old tenders.

    :param session: ClientSession
    :param tender_id: str Id of particular tender
    """
    tender = await get_object_data(session, tender_id)
    if datetime.fromisoformat(tender["dateCreated"]) >= CRAWLER_START_DATE:
        await process_tender(tender)


async def risks_data_handler(session, items):
    process_items_tasks = []
    for item in items:
        coroutine = fetch_and_process_tender(session, item["id"])
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    setup_logging()
    logger.info("Tender crawler started")
    main(risks_data_handler, init_task=init_mongodb)
