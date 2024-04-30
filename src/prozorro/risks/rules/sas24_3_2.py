from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import is_winner_awarded, count_winner_disqualifications_and_bidders
from prozorro.risks.settings import SAS_24_RULES_FROM


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-2"
    owner = "sas24"
    name = "Замовник відхилив тендерні пропозиції всіх учасників під час закупівлі товарів або послуг, крім переможця"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник дискваліфікував усіх учасників лота або процедури "
        "(якщо вона однолотова), окрім переможця."
    )
    legitimateness = ""
    development_basis = "Цей індикатор було розроблено, щоб виявляти можливі змови Замовника з Учасником."
    procurement_methods = ("aboveThresholdUA", "aboveThreshold", "aboveThresholdEU", "belowThreshold")
    tender_statuses = ("active.qualification", "active.awarded", "complete")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
        "defense",
    )
    procurement_categories = ("goods", "services")
    value_for_services = 400000
    start_date = SAS_24_RULES_FROM

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, value=True) and is_winner_awarded(tender):
            if len(tender.get("lots", [])):
                for lot in tender.get("lots", []):
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    disqualifications_count, winner_count, bidders_count = count_winner_disqualifications_and_bidders(
                        tender,
                        lot,
                        check_winner=True,
                    )

                    # Якщо для лота “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”.
                    if bidders_count == winner_count + disqualifications_count:
                        return RiskFound()
            else:
                disqualifications_count, winner_count, bidders_count = count_winner_disqualifications_and_bidders(
                    tender,
                    check_winner=True,
                )

                # Якщо “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”
                if bidders_count == winner_count + disqualifications_count:
                    return RiskFound()
        return RiskNotFound()
