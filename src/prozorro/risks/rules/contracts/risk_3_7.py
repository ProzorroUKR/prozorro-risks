import logging
from datetime import datetime

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule
from prozorro.risks.utils import fetch_tender


CONTRACT_MODIFYING_DAYS_LIMIT = 60
logger = logging.getLogger(__name__)


class RiskRule(BaseRiskRule):
    identifier = "3-7"
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

    async def process_tender(self, contract):
        if contract["status"] in self.contract_statuses:
            # В контракті по полю data.tender_id знаходимо відповідний тендер
            tender = await fetch_tender(contract["tender_id"])
            if (
                tender["procurementMethodType"] in self.procurement_methods
                and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
                and tender.get("mainProcurementCategory") in self.procurement_categories
            ):
                for tender_contract in tender.get("contracts", []):
                    # Якщо дата в контракті data.dateModified відрізняється менше ніж на 60 днів
                    # від дати в тендері data.contracts.date, індикатор приймає значення 1, розрахунок завершується
                    if (
                        tender_contract["id"] == contract["id"]
                        and (
                            datetime.fromisoformat(contract["dateModified"])
                            - datetime.fromisoformat(tender_contract["date"])
                        ).days
                        < CONTRACT_MODIFYING_DAYS_LIMIT
                    ):
                        return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found
