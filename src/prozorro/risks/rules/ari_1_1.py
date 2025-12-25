from datetime import datetime

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.settings import CRAWLER_START_DATE


class RiskRule(BaseContractRiskRule):
    identifier = "ari-1-1"
    owner = "ari"
    name = (
        "Публікація в електронній системі 3х і більше додаткових угод до договору"
    )
    description = (
        "Визначення закупівель, що містять ознаки безпідставних/ необґрунтованих заключень додаткових угод "
        "до договору про закупівлю, та/або свідчать про ймовірність допущення таких порушень."
    )
    # legitimateness = (
    #     "Зміна суми договру частіше ніж один раз на 90 днів є порушенням пп. 2, п. 5 статті 41 Закону "
    #     "про публічні закупівлі"
    # )
    # development_basis = (
    #     "Автоматичний контроль терміном внесення змін до договору відсутній в системі."
    # )
    contract_statuses = ("active",)
    stop_assessment_status = "terminated"
    procurement_methods = (
        "aboveThresholdUA",
        "aboveThresholdEU",
        "aboveThreshold",
        "belowThreshold",
        "reporting",
        "competitiveOrdering",
        "simple.defense",
        "priceQuotation",
        "negotiation",
        "negotiation.quick",
    )
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
        "defense",
    )
    value_for_services = 400000
    value_for_works = 1500000

    async def process_contract(self, contract, parent_object=None):
        if contract["status"] in self.contract_statuses:
            if datetime.fromisoformat(parent_object["dateCreated"]) < CRAWLER_START_DATE:
                raise SkipException()
            if self.tender_matches_requirements(
                parent_object, status=False, category=False, value=True
            ):
                active_quality_changes = 0
                for change in contract.get("changes", []):
                    if change["status"] == "active":
                        active_quality_changes += 1
                # Якщо в договорі є 3 і більш зміни data.changes і
                # data.changes.status='active', індикатор приймає значення 1.
                if active_quality_changes >= 3:
                    return RiskFound(type="contract", id=contract["id"])
        elif contract["status"] == self.stop_assessment_status:
            return RiskFromPreviousResult(type="contract", id=contract["id"])
        return RiskNotFound(type="contract", id=contract["id"])
