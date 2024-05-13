from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import (
    count_days_between_two_dates,
    get_complaints,
    flatten,
)
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
            # Якщо від complaints.dateDesision до поточної дати пройшло більше 30 днів, індикатор дорівнює 1.
            if (
                count_days_between_two_dates(get_now(), complaint["dateDecision"])
                > DECISION_LIMIT
            ):
                return RiskFound()
        return RiskNotFound()

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False):
            complaints = get_complaints(tender, statuses=["satisfied"])
            award_complaints = flatten(
                [
                    get_complaints(award, statuses=["satisfied"])
                    for award in tender.get("awards", [])
                ]
            )
            cancellation_complaints = flatten(
                [
                    get_complaints(cancellation, statuses=["satisfied"])
                    for cancellation in tender.get("cancellations", [])
                ]
            )
            qualifications_complaints = flatten(
                [
                    get_complaints(qualification, statuses=["satisfied"])
                    for qualification in tender.get("qualifications", [])
                ]
            )

            # Якщо в процедурі присутні блоки data.complaints, data.awards.complaints, data.qualification:complaints
            # або data.cancellations:complaints. що мають complaints.type='complaint' та complaints.status = 'satisfied'
            # то для кожного такого блоку порівнюємо complaints.dateDesision з поточною датой.
            if qualifications_complaints:
                return self.check_decision_delta(qualifications_complaints)

            if complaints:
                return self.check_decision_delta(complaints)

            if award_complaints:
                return self.check_decision_delta(award_complaints)

            if cancellation_complaints:
                return self.check_decision_delta(cancellation_complaints)
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
