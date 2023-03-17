from datetime import datetime

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule
from prozorro.risks.historical_data import get_list_of_cpvs


class RiskRule(BaseRiskRule):
    identifier = "2-15"
    name = "Закупівля товарів та послуг у одного учасника"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник проводить закупівлі у одного постачальника за 4 "
        "або більше різним кодам предметів закупівлі."
    )
    legitimateness = "Індикатор вводиться для ідентифікації можливої змови замовника та постачальника."
    development_basis = (
        "Цей індикатор було розроблено, оскільки система не зберігає зведену історію закупівель для замовника."
    )
    procurement_methods = ("aboveThresholdUA", "aboveThresholdEU")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    procurement_categories = ("goods", "services")

    async def process_tender(self, tender):
        if (
            tender["procurementMethodType"] in self.procurement_methods
            and tender["status"] in self.tender_statuses
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
            and tender.get("mainProcurementCategory") in self.procurement_categories
        ):
            active_awards = [award for award in tender.get("awards", []) if award["status"] == "active"]
            # Якщо в процедурі немає жодного об’єкту data.awards, що має статус data.awards.status='active',
            # індикатор приймає значення -2, розрахунок завершується.
            if not active_awards:
                return RiskIndicatorEnum.can_not_be_assessed

            for award in active_awards:
                for supplier in award.get("suppliers", []):
                    # Перевіряємо, що закупав замовник у конкретного постачальника протягом календарного року
                    supplier_identifier = supplier.get("identifier", {})
                    year = datetime.fromisoformat(tender["dateCreated"]).year
                    result = await get_list_of_cpvs(
                        year=year,
                        entity_identifier=tender["procuringEntityIdentifier"],
                        supplier_identifier=supplier_identifier,
                        procurement_methods=self.procurement_methods,
                    )

                    # За ідентифікатором замовника та ідентифікатором перможця рахуємо коди CPV.
                    # Якщо кількість унікальних предметів закупівлі 4 або більше, індикатор приймає значення 1.
                    if len(result.get("cpv", [])) >= 4:
                        return RiskIndicatorEnum.risk_found

                    # Якщо кількість предметів закупівлі дорівнює 3, то перевіряємо, чи входить у список
                    # в рядку поточні коди предметів закупівлі. Якщо хоч один не входить у список,
                    # індикатор приймає значення 1,
                    elif len(result.get("cpv", [])) == 3:
                        classifications = set()
                        for item in tender.get("items", []):
                            if not len(tender.get("lots", [])) or item.get("relatedLot") == award.get("relatedLot"):
                                classifications.add(item["classification"]["id"])
                        if len(classifications.difference(set(result["cpv"]))):
                            return RiskIndicatorEnum.risk_found
        return RiskIndicatorEnum.risk_not_found
