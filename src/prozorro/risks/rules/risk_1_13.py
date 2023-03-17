from datetime import datetime

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule
from prozorro.risks.utils import get_now


DECISION_LIMIT = 30


class RiskRule(BaseRiskRule):
    identifier = "1-13"
    name = "Невиконання замовником рішення органу оскарження"
    description = (
        "Індикатор свідчить про: Невиконання замовником рішення органу оскарження у встановлений "
        "зконом термін."
    )
    legitimateness = (
        "Стаття 18 частина 22: “Рішення органу оскарження набирають чинності з дня їх прийняття та є "
        "обов’язковими для виконання замовниками, особами, яких вони стосуються. Якщо рішення органу "
        "оскарження, прийняте за результатами розгляду органу оскарження, не було оскаржене до суду, "
        "таке рішення має бути виконано не пізніше 30 днів з дня його прийняття органом оскарження.”"
    )
    development_basis = (
        "Свідчить про ймовірне порушення вимог частини 22 статті 18 Закону. Автоматичний контроль "
        "за виконанням рішень Органу оскаржень наразі відсутній в систем закупівель;"
    )
    procurement_methods = (
        "negotiation",
        "negotiation.quick",
        "aboveThresholdEU",
        "aboveThresholdUA",
    )
    tender_statuses = (
        "active",
        "active.tendering",
        "active.prequalification",
        "active.pre-qualification.stand-still",
        "active.pre-qualification",
        "active.qualification",
        "active.awarded",
    )
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    @staticmethod
    def get_satisfied_complaints(obj):
        complaints = []
        for complaint in obj.get("complaints", []):
            if complaint["type"] == "complaint" and complaint["status"] == "satisfied":
                complaints.append(complaint)
        return complaints

    @staticmethod
    def check_decision_delta(complaints):
        for complaint in complaints:
            if (
                get_now() - datetime.fromisoformat(complaint["dateDecision"])
            ).days > DECISION_LIMIT:
                return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found

    def process_tender(self, tender):
        if (
            tender["procurementMethodType"] in self.procurement_methods
            and tender["status"] in self.tender_statuses
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
        ):
            complaints = self.get_satisfied_complaints(tender)
            award_complaints = sum(
                [
                    self.get_satisfied_complaints(award)
                    for award in tender.get("awards", [])
                ],
                [],
            )

            if complaints:
                return self.check_decision_delta(complaints)

            if award_complaints:
                return self.check_decision_delta(award_complaints)
            return RiskIndicatorEnum.can_not_be_assessed
        return RiskIndicatorEnum.risk_not_found
