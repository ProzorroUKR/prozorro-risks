from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import has_milestone_24


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-13"
    owner = "sas24"
    name = (
        'Безпідставне застосування замовником під час спрощеної закупівлі механізму усунення '
        'невідповідностей "24 години"'
    )
    description = (
        'Визначення закупівель, що містять ознаки розміщення замовником в електронній системі закупівель повідомлення '
        'з вимогою про усунення невідповідностей та проводить спрощену закупівлю, крім державних замовників '
        'в розумінні Закону України "Про оборонні закупівлі", та/або свідчать про ймовірність допущення таких порушень.'
    )
    legitimateness = (
        'Стаття 14 Закону України "Про публічні закупівлі"'
    )
    development_basis = (
        'Ознака порушення статті 14 Закону України "Про публічні закупівлі", якою не визначено '
        'механізму усунення невідповідностей у пропозиціях учасників'
    )
    procurement_methods = (
        "belowThreshold",
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
    )
    value_for_services = 400000
    value_for_works = 1500000

    @staticmethod
    def awards_have_milestone_24_code(tender, lot=None):
        for award in tender.get("awards", []):
            if (not lot or lot["id"] == award["lotID"]) and has_milestone_24(award):
                return True

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True):
            if tender.get("lots"):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    if self.awards_have_milestone_24_code(tender, lot=lot):
                        return RiskFound()
            else:
                if self.awards_have_milestone_24_code(tender):
                    return RiskFound()
        return RiskNotFound()
