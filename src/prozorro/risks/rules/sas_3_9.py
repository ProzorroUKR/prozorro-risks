from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import get_complaints


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-9"
    name = "Повторне визнання переможцем учасника після винесення рішення органом оскарження по ньому"
    procurement_methods = ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    @staticmethod
    def tender_has_active_awards_with_same_bid(awards, current_award):
        # перевіряємо чи є ще інші data.awards в статусі data.awards.status= "active"
        # із таким же data.awards.bid_id та lotID
        active_awards = [
            award
            for award in awards
            if all(
                [
                    award["id"] != current_award["id"],
                    award["status"] == "active",
                    award["bid_id"] == current_award["bid_id"],
                    award["lotID"] == current_award["lotID"] if current_award.get("lotID") else True,
                ]
            )
        ]
        return len(active_awards) > 0

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False):
            for award in tender.get("awards", []):
                # Шукаємо в процедурі блоки data.awards.complaints, що мають complaints.type='complaint'
                complaints = get_complaints(award)
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
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
