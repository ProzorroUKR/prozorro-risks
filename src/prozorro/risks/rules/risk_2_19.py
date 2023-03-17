from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "2-19"
    name = "Відхилення 3-х і більше тендерних пропозицій/пропозицій"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник відхиляє три або більше тендерних пропозиції, "
        "які за результатами оцінки визначені найбільш економічно вигідними."
    )
    legitimateness = (
        "Порушення принципів здійснення закупівель, що викладені у статті 5 Закону України "
        "'Про публічні закупівлі'."
    )
    development_basis = "Цей індикатор було розроблено для виявлення ознак змови замовника з постачальником(ками)."
    procurement_methods = ("aboveThresholdEU", "aboveThresholdUA")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    def process_tender_with_cancelled_proposition(self, tender, lots_limit):
        if (
            tender["procurementMethodType"] in self.procurement_methods
            and tender["status"] in self.tender_statuses
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
        ):
            unsuccessful_awards = [
                award for award in tender["awards"] if award["status"] == "unsuccessful"
            ]
            if not unsuccessful_awards:
                return RiskIndicatorEnum.can_not_be_assessed
            active_bids = [bid for bid in tender["bids"] if bid["status"] == "active"]
            if len(tender.get("lots", 0)):
                disqualified_lots_count = 0
                related_active_bid_count = 0
                for lot in tender["lots"]:
                    for award in unsuccessful_awards:
                        if award.get("lotID") == lot["id"]:
                            disqualified_lots_count += 1
                    for bid in active_bids:
                        if bid.get("relatedLot") == lot["id"]:
                            related_active_bid_count += 1
                    if (
                        disqualified_lots_count == lots_limit
                        and related_active_bid_count > disqualified_lots_count + 2
                    ):
                        return RiskIndicatorEnum.risk_found
            else:
                if (
                    len(unsuccessful_awards) == lots_limit
                    and len(active_bids) > len(unsuccessful_awards) + 2
                ):
                    return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found

    def process_tender(self, tender):
        return self.process_tender_with_cancelled_proposition(tender, lots_limit=3)
