from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import count_days_between_two_dates, get_satisfied_complaints, flatten
from prozorro.risks.utils import get_now

DECISION_LIMIT = 30


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-1"
    name = "Невиконання замовником рішення органу оскарження"
    description = (
        "Індикатор свідчить про: Невиконання замовником рішення органу оскарження у встановлений законом термін."
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
        "aboveThreshold",
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
    def check_decision_delta(complaints):
        for complaint in complaints:
            if count_days_between_two_dates(get_now(), complaint["dateDecision"]) > DECISION_LIMIT:
                return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found

    async def process_tender(self, tender):
        if self.tender_matches_requirements(tender, category=False):
            complaints = get_satisfied_complaints(tender)
            award_complaints = flatten([get_satisfied_complaints(award) for award in tender.get("awards", [])])

            if complaints:
                return self.check_decision_delta(complaints)

            if award_complaints:
                return self.check_decision_delta(award_complaints)
        elif tender.get("status") == self.stop_assessment_status:
            return RiskIndicatorEnum.use_previous_result
        return RiskIndicatorEnum.risk_not_found
