import logging
from datetime import datetime, timedelta

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.settings import CRAWLER_START_DATE, OLD_SAS_RISKS_END_DATE
from prozorro.risks.rules.utils import calculate_end_date

CONTRACT_MODIFYING_DAYS_LIMIT = 60
logger = logging.getLogger(__name__)


class RiskRule(BaseContractRiskRule):
    identifier = "sas-3-7"
    name = "Короткий строк виконання договору при закупівлі робіт"
    description = (
        "Дата оприлюднення договору на роботи  і дата звіту про виконання договору відрізняються менше, ніж на 60 днів"
    )
    contract_statuses = ("terminated",)
    procurement_methods = ("aboveThresholdUA", "aboveThresholdEU", "aboveThreshold")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    procurement_categories = ("works",)
    end_date = OLD_SAS_RISKS_END_DATE

    async def process_contract(self, contract, parent_object=None):
        if contract["status"] in self.contract_statuses:
            if datetime.fromisoformat(parent_object["dateCreated"]) < CRAWLER_START_DATE:
                raise SkipException()
            if self.tender_matches_requirements(parent_object, status=False):
                for tender_contract in parent_object.get("contracts", []):
                    # Якщо дата в контракті data.dateModified відрізняється менше ніж на 60 днів
                    # від дати в тендері data.contracts.date, індикатор приймає значення 1, розрахунок завершується
                    if tender_contract["id"] == contract["id"]:
                        calculated_date = calculate_end_date(
                            tender_contract["date"],
                            timedelta(days=CONTRACT_MODIFYING_DAYS_LIMIT),
                        )
                        if datetime.fromisoformat(contract["dateModified"]) < calculated_date:
                            return RiskFound(type="contract", id=contract["id"])
        return RiskNotFound(type="contract", id=contract["id"])
