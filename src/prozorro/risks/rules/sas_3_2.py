from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseTenderRiskRule


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

    @staticmethod
    def bidder_applies_on_lot(bid, lot):
        for lot_value in bid.get("lotValues", []):
            if lot_value["relatedLot"] == lot["id"]:
                return True
        return False

    async def process_tender(self, tender):
        if self.tender_matches_requirements(tender):
            for lot in tender.get("lots", []):
                if lot["status"] in ("cancelled", "unsuccessful"):
                    continue
                disqualified_awards = set()
                winner_count = 0
                bidders = set()
                for award in tender.get("awards", []):
                    if award.get("lotID") == lot["id"] and award["status"] == "unsuccessful":
                        for supplier in award.get("suppliers", []):
                            disqualified_awards.add(
                                f'{supplier["identifier"]["scheme"]}-{supplier["identifier"]["id"]}'
                            )
                    elif award["lotID"] == lot["id"] and award["status"] == "active":
                        winner_count = 1

                if not disqualified_awards or not winner_count:
                    return RiskIndicatorEnum.risk_not_found

                disqualifications_count = len(disqualified_awards)
                if disqualifications_count <= 2:
                    return RiskIndicatorEnum.risk_not_found

                for bid in tender.get("bids", []):
                    if bid["status"] == "active" and self.bidder_applies_on_lot(bid, lot):
                        for tenderer in bid.get("tenderers", []):
                            bidders.add(f'{tenderer["identifier"]["scheme"]}-{tenderer["identifier"]["id"]}')
                bidders_count = len(bidders)

                if bidders_count == winner_count + disqualifications_count:
                    return RiskIndicatorEnum.risk_found
        elif tender.get("status") == self.stop_assessment_status:
            return RiskIndicatorEnum.use_previous_result
        return RiskIndicatorEnum.risk_not_found