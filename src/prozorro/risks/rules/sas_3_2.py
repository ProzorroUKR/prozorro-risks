from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import count_winner_disqualifications_and_bidders


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-2"
    name = "Замовник відхилив тендерні пропозиції всіх учасників під час закупівлі товарів або послуг, крім переможця"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник дискваліфікував усіх учасників лота або процедури "
        "(якщо вона однолотова), окрім переможця."
    )
    legitimateness = ""
    development_basis = "Цей індикатор було розроблено, щоб виявляти можливі змови Замовника з Учасником."
    procurement_methods = ("aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    procurement_categories = ("goods", "services")

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender):
            if len(tender.get("lots", [])):
                for lot in tender.get("lots", []):
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    disqualifications_count, winner_count, bidders_count = count_winner_disqualifications_and_bidders(
                        tender,
                        lot,
                    )

                    if not disqualifications_count or not winner_count:
                        continue

                    if disqualifications_count <= 2:
                        continue

                    # Якщо для лота “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”.
                    if bidders_count == winner_count + disqualifications_count:
                        return RiskFound()
            else:
                disqualifications_count, winner_count, bidders_count = count_winner_disqualifications_and_bidders(
                    tender,
                )

                if not disqualifications_count or not winner_count:
                    return RiskNotFound()

                # Якщо кількість таких об’єктів менше або дорівнює 2, то індикатор дорівнює “0”
                if disqualifications_count <= 2:
                    return RiskNotFound()

                # Якщо “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”
                if bidders_count == winner_count + disqualifications_count:
                    return RiskFound()
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
