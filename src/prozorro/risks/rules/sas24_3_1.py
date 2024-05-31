from datetime import timedelta

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import (
    calculate_end_date,
    get_complaints,
    flatten,
)
from prozorro.risks.settings import SAS_24_RULES_FROM
from prozorro.risks.utils import get_now

DECISION_LIMIT = 30


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-1"
    owner = "sas24"
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
        "complete",
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

    @staticmethod
    def check_decision_delta(complaints):
        for complaint in complaints:
            # Якщо від complaints.dateDecision до поточної дати пройшло більше 30 днів, індикатор дорівнює 1.
            calculated_date = calculate_end_date(complaint["dateDecision"], timedelta(days=DECISION_LIMIT))
            if get_now() > calculated_date:
                return RiskFound()
        return RiskNotFound()

    async def process_tender(self, tender, parent_object=None):
        from prozorro.risks.crawlers.delay_crawler import logger
        if get_now() > calculate_end_date(tender["dateModified"], -timedelta(days=DECISION_LIMIT), ceil=False):
            logger.error(f"Tender {tender['id']} has been modified less than 30 days ago")
            raise SkipException()
        if self.tender_matches_requirements(tender, category=False, value=True):
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
            # то для кожного такого блоку порівнюємо complaints.dateDecision з поточною датой.
            if qualifications_complaints:
                return self.check_decision_delta(qualifications_complaints)

            if complaints:
                return self.check_decision_delta(complaints)

            if award_complaints:
                return self.check_decision_delta(award_complaints)

            if cancellation_complaints:
                return self.check_decision_delta(cancellation_complaints)
        return RiskNotFound()
