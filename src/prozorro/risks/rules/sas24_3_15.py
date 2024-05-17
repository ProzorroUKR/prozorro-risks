from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import (
    is_winner_awarded,
    count_winner_disqualifications_and_bidders,
    flatten,
    get_complaints,
)
from prozorro.risks.settings import SAS_24_RULES_FROM


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-15"
    owner = "sas24"
    name = (
        "Замовник відхилив мінімум 2 учасників за наявності скарги в Органі оскарження"
    )
    description = (
        "Визначення закупівель, що містять ознаки повторного відхилення замовником тендерної пропозиції учасника "
        "після винесення рішення Органом оскарження по такому учаснику, та/або свідчать про ймовірність "
        "допущення таких порушень"
    )
    legitimateness = (
        'Пункту 44 Особливостей № 1178, статті 31 Закону України "Про публічні закупівлі"'
    )
    development_basis = (
        'Ознака безпідставного відхилення тендерних пропозицій/ пропозицій учасників на порушення вимог '
        'пункту 44 Особливостей № 1178, статті 31 Закону України "Про публічні закупівлі" '
        'з метою надання переваги конкретному учаснику'
    )
    procurement_methods = (
        "aboveThresholdEU",
        "aboveThresholdUA",
        "aboveThreshold",
    )
    tender_statuses = (
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

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True) and is_winner_awarded(tender):
            if tender.get("lots"):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    disqualifications_count, winner_count, _ = count_winner_disqualifications_and_bidders(
                        tender,
                        lot,
                        check_winner=True,
                    )
                    award_complaints = flatten(
                        [
                            get_complaints(award, statuses=["resolved"])
                            for award in tender.get("awards", [])
                            if award.get("lotID") == lot["id"]
                        ]
                    )
                    if disqualifications_count >= 2 and award_complaints:
                        return RiskFound()
            else:
                disqualifications_count, winner_count, _ = count_winner_disqualifications_and_bidders(
                    tender,
                    check_winner=True,
                )
                award_complaints = flatten(
                    [
                        get_complaints(award, statuses=["resolved"])
                        for award in tender.get("awards", [])
                    ]
                )
                if disqualifications_count >= 2 and award_complaints:
                    return RiskFound()
        return RiskNotFound()
