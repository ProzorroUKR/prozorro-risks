import logging
from datetime import datetime, timedelta

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.settings import CRAWLER_START_DATE, SAS_24_RULES_FROM
from prozorro.risks.rules.utils import calculate_end_date

CONTRACT_MODIFYING_DAYS_LIMIT = 60
logger = logging.getLogger(__name__)


class RiskRule(BaseContractRiskRule):
    identifier = "sas24-3-7"
    owner = "sas24"
    name = "Короткий строк виконання договору при закупівлі робіт"
    description = (
        "Дата оприлюднення договору на роботи  і дата звіту про виконання договору відрізняються менше, ніж на 60 днів"
    )
    contract_statuses = ("active",)
    stop_assessment_status = "terminated"
    procurement_methods = (
        "negotiation",
        "negotiation.quick",
        "aboveThresholdUA",
        "aboveThresholdEU",
        "aboveThreshold",
        "belowThreshold",
        "reporting",
    )
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
        "defense",
    )
    procurement_categories = ("works",)
    value_for_works = 1500000
    start_date = SAS_24_RULES_FROM

    async def process_contract(self, contract, parent_object=None):
        if contract["status"] in self.contract_statuses:
            if (
                datetime.fromisoformat(parent_object["dateCreated"])
                < CRAWLER_START_DATE
            ):
                raise SkipException()
            if self.tender_matches_requirements(
                parent_object, status=False, value=True
            ):
                for tender_contract in parent_object.get("contracts", []):
                    # Якщо дата в контракті data.period.endDate відрізняється менше ніж на 60 днів
                    # від дати в тендері data.contracts.date, індикатор приймає значення 1, розрахунок завершується
                    if (
                        tender_contract["id"] == contract["id"]
                        and contract.get("period", {}).get("endDate")
                        and datetime.fromisoformat(contract["period"]["endDate"])
                        < calculate_end_date(
                            tender_contract["date"],
                            timedelta(days=CONTRACT_MODIFYING_DAYS_LIMIT),
                        )
                    ):
                        return RiskFound(type="contract", id=contract["id"])
        elif contract["status"] == self.stop_assessment_status:
            return RiskFromPreviousResult(type="contract", id=contract["id"])
        return RiskNotFound(type="contract", id=contract["id"])
