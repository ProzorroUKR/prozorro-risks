import sys
from prozorro_crawler.main import main
from prozorro.risks.crawlers.base import process_risks
from prozorro.risks.db import init_mongodb, update_tender_risks
from prozorro.risks.logging import setup_logging
from prozorro.risks.requests import get_object_data
from prozorro.risks.utils import get_now
from prozorro.risks.rules import *  # noqa
import asyncio
import logging


logger = logging.getLogger(__name__)

RISK_RULES_MODULE = "prozorro.risks.rules"
RISK_MODULES = sys.modules[RISK_RULES_MODULE].__all__
CONTRACT_RISKS = []
for module_name in RISK_MODULES:
    risk_module = getattr(sys.modules[RISK_RULES_MODULE], module_name)
    risk_rule = getattr(risk_module, "RiskRule")()
    if hasattr(risk_rule, "process_contract"):
        CONTRACT_RISKS.append(risk_rule)
API_RESOURCE = "contracts"


async def process_contract(contract):
    """
    Process contract with provided risk rules and save results to database
    :param contract: dict Contract data
    """
    uid = contract.get("tender_id")
    risks = await process_risks(contract, CONTRACT_RISKS, resource=API_RESOURCE)
    if risks:
        await update_tender_risks(
            uid,
            risks,
            {"dateAssessed": get_now().isoformat()},
        )


async def fetch_and_process_contract(session, contract_id):
    """
    Fetch more detailed information about contract and process tender whether it has risks

    :param session: ClientSession
    :param contract_id: str Id of particular contract
    """
    contract = await get_object_data(session, contract_id, resource=API_RESOURCE)
    await process_contract(contract)


async def risks_data_handler(session, items):
    process_items_tasks = []
    for item in items:
        coroutine = fetch_and_process_contract(session, item["id"])
        process_items_tasks.append(coroutine)
    await asyncio.gather(*process_items_tasks)


if __name__ == "__main__":
    setup_logging()
    logger.info("Contract crawler started")
    main(risks_data_handler, init_task=init_mongodb)
