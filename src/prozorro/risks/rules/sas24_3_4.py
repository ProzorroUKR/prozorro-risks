from datetime import datetime

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.settings import CRAWLER_START_DATE, SAS_24_RULES_FROM
from prozorro.risks.utils import fetch_tender


class RiskRule(BaseContractRiskRule):
    identifier = "sas24-3-4"
    owner = "sas24"
    name = "Зміна істотних умов договору (ціни за одиницю товару)"
    description = "Індикатор свідчить про незаконну зміну ціни договору частіше ніж один раз у 90 днів"
    legitimateness = (
        "Зміна суми договру частіше ніж один раз на 90 днів є порушенням пп. 2, п. 5 статті 41 Закону "
        "про публічні закупівлі"
    )
    development_basis = "Автоматичний контроль терміном внесення змін до договору відсутній в системі."
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
    value_for_services = 400000
    value_for_works = 1500000
    start_date = SAS_24_RULES_FROM

    async def process_contract(self, contract):
        if contract["status"] in self.contract_statuses:
            # В контракті по полю data.tender_id знаходимо відповідний тендер
            tender = await fetch_tender(contract["tender_id"])
            if datetime.fromisoformat(tender["dateCreated"]) < CRAWLER_START_DATE:
                raise SkipException()
            if self.tender_matches_requirements(tender, status=False, category=False, value=True):
                rationales = {"itemPriceVariation", "durationExtension", "fiscalYearExtension"}
                active_changes = [
                    change
                    for change in contract.get("changes", [])
                    if change["status"] == "active" and len(rationales.intersection(set(change["rationaleTypes"]))) >= 2
                ]
                # Якщо в договорі є зміни у яких data.changes.status='active' та
                # в масив причин data.changes.rationaleTypes містить елементи itemPriceVariation та durationExtension,
                # або itemPriceVariation та fiscalYearExtension, або itemPriceVariation та fiscalYearExtension та
                # durationExtension, то індикатор приймає значення 1, розрахунок завершується
                if active_changes:
                    return RiskFound(type="contract", id=contract["id"])
        elif contract["status"] == self.stop_assessment_status:
            return RiskFromPreviousResult(type="contract", id=contract["id"])
        return RiskNotFound(type="contract", id=contract["id"])
