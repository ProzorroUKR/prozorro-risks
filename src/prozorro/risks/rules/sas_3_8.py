from datetime import datetime

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import get_complaints


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-8"
    name = "Застосування 24 годин після винесення рішення органом оскарження по постачальнику"
    procurement_methods = ("aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    @staticmethod
    def tender_has_another_award_with_same_bid_and_milestone(award, awards_with_milestones):
        # перевіряємо чи є ще інші data.awards із таким же data.awards.bid_id,
        # в яких є об'єкт data.award.milestones.code="24h"
        for award_with_milestone in awards_with_milestones:
            if award["id"] != award_with_milestone["id"] and award["bid_id"] == award_with_milestone["bid_id"]:
                for complaint in award["complaints"]:
                    if any(
                        datetime.fromisoformat(date) > datetime.fromisoformat(complaint.get("date"))
                        for date in award_with_milestone["day_milestones_dates"]
                    ):
                        return True
        return False

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False):
            # Шукаємо в процедурі блоки data.awards.complaints, що мають complaints.type='complaint',
            # а також data.award.milestones.code="24h"
            awards_with_complaints = []
            awards_with_milestones = []
            for award in tender.get("awards", []):
                if award_complaints := get_complaints(award):
                    award["complaints"] = award_complaints
                    awards_with_complaints.append(award)
                day_milestones_dates = [
                    milestone.get("date") for milestone in award.get("milestones", []) if milestone["code"] == "24h"
                ]
                if day_milestones_dates:
                    award["day_milestones_dates"] = day_milestones_dates
                    awards_with_milestones.append(award)
            # Якщо в процедурі присутні блоки data.awards.complaints, із complaints.type='complaint',
            # то для кожного такого блоку перевіряємо чи є ще інші data.awards із таким же data.awards.bid_id,
            # в яких є об'єкт data.award.milestones.code="24h".
            for award in awards_with_complaints:
                # Якщо процедура має лоти, то розрахунок проводимо лише для лотів data.lots.id,
                # у яких є data.awards.complaints, на які посилається data.awards.lotID=data.lots.id.
                if len(tender.get("lots", [])):
                    for lot in tender["lots"]:
                        if lot["status"] not in ("cancelled", "unsuccessful") and lot["id"] == award["lotID"]:
                            if self.tender_has_another_award_with_same_bid_and_milestone(award, awards_with_milestones):
                                return RiskFound()
                elif self.tender_has_another_award_with_same_bid_and_milestone(award, awards_with_milestones):
                    return RiskFound()
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
