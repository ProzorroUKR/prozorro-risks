from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-5"
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

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False):
            # Визначаємо кількість дискваліфікацій
            unsuccessful_awards = [award for award in tender["awards"] if award["status"] == "unsuccessful"]

            # Якщо в процедурі немає жодного об’єкту зі статусом data.awards.status='unsuccessful',
            # індикатор приймає значення 0
            if not unsuccessful_awards:
                return RiskNotFound()

            if len(tender.get("lots", [])):
                for lot in tender["lots"]:
                    disqualified_lots_count = 0
                    # Визначаємо кількість дискваліфікацій - кількість об’єктів data.awards, що посилаються
                    # на лот data.awards.lotID=data.lots.id та мають data.awards.status='unsuccessful'
                    for award in unsuccessful_awards:
                        if award.get("lotID") == lot["id"] and lot["status"] not in ("cancelled", "unsuccessful"):
                            disqualified_lots_count += 1
                    # Якщо кількість дискваліфікацій дорівнює 2 або більше, індикатор приймає значення 1
                    if disqualified_lots_count >= 2:
                        return RiskFound()
            else:
                # Якщо процедура не має лотів i кількість дискваліфікацій дорівнює 2 або більше,
                # індикатор приймає значення 1
                if len(unsuccessful_awards) >= 2:
                    return RiskFound()
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
