from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "3-5"
    name = "Замовник відхилив мінімум 2 учасників"
    description = "Даний індикатор виявляє ситуації, коли замовник відхиляє мінімум 2 учасників"
    legitimateness = (
        "Порушення принципів здійснення закупівель, що викладені у статті 5 Закону України 'Про публічні закупівлі'."
    )
    development_basis = "Цей індикатор було розроблено для виявлення ознак змови замовника з постачальником(ками)."
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
        if (
            tender["procurementMethodType"] in self.procurement_methods
            and tender["status"] in self.tender_statuses
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
        ):
            # Визначаємо кількість дискваліфікацій
            unsuccessful_awards = [award for award in tender["awards"] if award["status"] == "unsuccessful"]

            # Якщо в процедурі немає жодного об’єкту зі статусом data.awards.status='unsuccessful',
            # індикатор приймає значення -2
            if not unsuccessful_awards:
                return RiskIndicatorEnum.can_not_be_assessed

            if len(tender.get("lots", 0)):
                disqualified_lots_count = 0
                for lot in tender["lots"]:
                    # Визначаємо кількість дискваліфікацій - кількість об’єктів data.awards, що посилаються
                    # на лот data.awards.lotID=data.lots.id та мають data.awards.status='unsuccessful'
                    for award in unsuccessful_awards:
                        if award.get("lotID") == lot["id"]:
                            disqualified_lots_count += 1
                    # Якщо кількість дискваліфікацій дорівнює 2 або більше, індикатор приймає значення 1
                    if disqualified_lots_count >= 2:
                        return RiskIndicatorEnum.risk_found
            else:
                # Якщо процедура не має лотів i кількість дискваліфікацій дорівнює 2 або більше,
                # індикатор приймає значення 1
                if len(unsuccessful_awards) >= 2:
                    return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found
