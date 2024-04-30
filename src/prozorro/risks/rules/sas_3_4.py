from datetime import datetime

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.settings import CRAWLER_START_DATE


class RiskRule(BaseContractRiskRule):
    identifier = "sas-3-4"
    name = "Зміна істотних умов договору (ціни за одиницю товару)"
    description = "Індикатор свідчить про незаконну зміну ціни договору частіше ніж один раз у 90 днів"
    legitimateness = (
        "Зміна суми договру частіше ніж один раз на 90 днів є порушенням пп. 2, п. 5 статті 41 Закону "
        "про публічні закупівлі"
    )
    development_basis = "Автоматичний контроль терміном внесення змін до договору відсутній в системі."
    contract_statuses = ("active",)
    stop_assessment_status = "terminated"
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    async def process_contract(self, contract, parent_object=None):
        if contract["status"] in self.contract_statuses:
            if datetime.fromisoformat(parent_object["dateCreated"]) < CRAWLER_START_DATE:
                raise SkipException()
            if parent_object.get("procuringEntity", {}).get("kind") in self.procuring_entity_kinds:
                active_changes = [
                    change
                    for change in contract.get("changes", [])
                    if change["status"] == "active" and "itemPriceVariation" in change["rationaleTypes"]
                ]
                # Якщо в договорі є зміни у яких data.changes.status='active' та
                # в масив причин data.changes.rationaleTypes містить елемент itemPriceVariation,
                # індикатор приймає значення 1, розрахунок завершується
                if active_changes:
                    return RiskFound(type="contract", id=contract["id"])
        elif contract["status"] == self.stop_assessment_status:
            return RiskFromPreviousResult(type="contract", id=contract["id"])
        return RiskNotFound(type="contract", id=contract["id"])
