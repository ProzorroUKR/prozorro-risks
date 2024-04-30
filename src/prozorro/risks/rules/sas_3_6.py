from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import count_percentage_between_two_values

PERCENTAGE_LIMIT = 30


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-6"
    name = "Явне завищення очікуваної вартості"
    description = "Сума вказана у повідомленні про намір укласти договір менша за очікувану вартість на 30% і більше"
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
            if len(tender.get("lots", [])):
                # Якщо процедура має лоти, то розрахунок проводимо в розрізі кожного лота
                # по data.awards.lotID=data.lots.id і перевіряємо різницю між data.awards.value.amount
                # та data.lots.value.amount відповідного лоту.
                for lot in tender["lots"]:
                    lot_value = lot.get("value", {}).get("amount", 0)
                    for award in tender.get("awards", []):
                        if award.get("lotID") == lot["id"] and lot["status"] not in ("cancelled", "unsuccessful"):
                            award_value = award.get("value", {}).get("amount", 0)

                            # Якщо різниця менша на 30% і більше індикатор приймає значення 1, розрахунок завершується.
                            if count_percentage_between_two_values(lot_value, award_value) >= PERCENTAGE_LIMIT:
                                return RiskFound()
            else:
                # Якщо процедура не має лотів, то перевіряємо різницю між data.awards.value.amount та data.value.amount.
                tender_value = tender.get("value", {}).get("amount", 0)
                for award in tender.get("awards", []):
                    award_value = award.get("value", {}).get("amount", 0)

                    # Якщо різниця менша на 30% і більше індикатор приймає значення 1, розрахунок завершується.
                    if count_percentage_between_two_values(tender_value, award_value) >= PERCENTAGE_LIMIT:
                        return RiskFound()
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
