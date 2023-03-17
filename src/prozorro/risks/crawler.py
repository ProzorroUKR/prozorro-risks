import sys

from prozorro_crawler.main import main
from prozorro.risks.db import init_mongodb, save_tender, update_tender_risks
from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.logging import setup_logging
from prozorro.risks.requests import get_tender_data
from prozorro.risks.utils import get_now
from prozorro.risks.rules import *  # noqa
import asyncio
import logging


logger = logging.getLogger(__name__)

RISK_RULES_MODULE = "prozorro.risks.rules"
RISK_RULE_MODULES = sys.modules[RISK_RULES_MODULE].__all__


async def process_tender(tender):
    risks = {
        "worked": [],
        "other": [],
    }
    uid = tender.pop("id" if "id" in tender else "_id")
    identifier = tender.get("procuringEntity", {}).get("identifier", {})
    tender["procuringEntityIdentifier"] = f'{identifier.get("scheme", "")}-{identifier.get("id", "")}'

    # for some risk rules it is required to have saved tenders in database for processing statistics
    await save_tender(uid, tender)

    for module_name in RISK_RULE_MODULES:
        risk_module = getattr(sys.modules[RISK_RULES_MODULE], module_name)
        risk_rule = getattr(risk_module, "RiskRule")()
        risk_indicator = await risk_rule.process_tender(tender)
        if risk_indicator == RiskIndicatorEnum.risk_found:
            risks["worked"].append(
                {
                    "id": risk_rule.identifier,
                    "name": risk_rule.name,
                    "description": risk_rule.description,
                    "legitimateness": risk_rule.legitimateness,
                    "development_basis": risk_rule.development_basis,
                    "indicator": risk_indicator,
                    "date": get_now().isoformat(),
                }
            )
        else:
            risks["other"].append(
                {
                    "id": risk_rule.identifier,
                    "indicator": risk_indicator,
                    "date": get_now().isoformat(),
                }
            )

    await update_tender_risks(
        uid,
        {
            "risks": risks,
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
    Fetch more detailed information about tender and process tender whether it has risks

    :param session: ClientSession
    :param tender_id: int Id of particular tender
    """
    tender = await get_tender_data(session, tender_id)
    await process_tender(tender)


async def risks_data_handler(session, items):
    process_items_tasks = []
    for item in items:
        coroutine = fetch_and_process_tender(session, item["id"])
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    setup_logging()
    logger.info("Crawler started")
    main(risks_data_handler, init_task=init_mongodb)
