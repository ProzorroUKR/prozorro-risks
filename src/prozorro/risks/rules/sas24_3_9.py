from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import get_complaints, count_days_between_two_dates, is_winner_awarded
from prozorro.risks.settings import SAS_24_RULES_FROM, WINNER_AWARDED_DAYS_LIMIT_FOR_OPEN_TENDERS
from prozorro.risks.utils import get_now


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-9"
    owner = "sas24"
    name = "Повторне визнання переможцем учасника після винесення рішення органом оскарження по ньому"
    procurement_methods = ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded", "complete")
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
    def tender_has_active_awards_with_same_bid(awards, current_award):
        # перевіряємо чи є ще інші data.awards в статусі data.awards.status= "active"
        # із таким же data.awards.bid_id та lotID, а поточна дата більша за дату визначення переможця
        # data.awards.date на 5 днів
        active_awards = [
            award
            for award in awards
            if all(
                [
                    award["id"] != current_award["id"],
                    award["status"] == "active",
                    award["bid_id"] == current_award["bid_id"],
                    award["lotID"] == current_award["lotID"] if current_award.get("lotID") else True,
                    award.get("date"),
                    count_days_between_two_dates(get_now(), award["date"]) > WINNER_AWARDED_DAYS_LIMIT_FOR_OPEN_TENDERS
                ]
            )
        ]
        return len(active_awards) > 0

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True) and is_winner_awarded(tender):
            for award in tender.get("awards", []):
                # Шукаємо в процедурі блоки data.awards.complaints, що мають complaints.type='complaint'
                # та complaints.status = 'satisfied',
                complaints = get_complaints(award, statuses=["satisfied", "resolved"])
                if not complaints:
                    continue

                # Якщо процедура має лоти, то розрахунок проводимо лише для лотів data.lots.id,
                # у яких є awards.complaints, на які посилається data.awards.lotID
                if len(tender.get("lots", [])):
                    for lot in tender["lots"]:
                        if lot["status"] not in ("cancelled", "unsuccessful") and lot["id"] == award["lotID"]:
                            if self.tender_has_active_awards_with_same_bid(tender["awards"], award):
                                return RiskFound()
                else:
                    if self.tender_has_active_awards_with_same_bid(tender["awards"], award):
                        return RiskFound()
        return RiskNotFound()
