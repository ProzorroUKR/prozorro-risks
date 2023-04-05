from datetime import datetime

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import get_satisfied_complaints


class RiskRule(BaseTenderRiskRule):
    identifier = "3-8"
    name = "Застосування 24 годин після винесення рішення органом оскарження по постачальнику"
    procurement_methods = ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    async def process_tender(self, tender):
        if self.tender_matches_requirements(tender, category=False):
            for award in tender.get("awards", []):
                # Шукаємо в процедурі блоки data.awards.complaints, що мають complaints.type='complaint'
                # та complaints.status = 'satisfied', а також data.award.milestones.code="24h"
                satisfied_complaints = get_satisfied_complaints(award)
                day_milestones_dates = [
                    milestone.get("date") for milestone in award.get("milestones", []) if milestone["code"] == "24h"
                ]

                # Якщо в процедурі присутні блоки data.awards.complaints, із complaints.type='complaint'
                # та complaints.status = 'satisfied', а також є data.award.milestones.code="24h",
                # то для кожного такого блоку порівнюємо complaints.dateDesision з award.milestones.date.
                if satisfied_complaints and day_milestones_dates:
                    for complaint in satisfied_complaints:
                        # Якщо award.milestones.date більше complaints.dateDesision, індикатор дорівнює 1
                        if any(
                            datetime.fromisoformat(date) > datetime.fromisoformat(complaint.get("dateDecision"))
                            for date in day_milestones_dates
                        ):
                            return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found
