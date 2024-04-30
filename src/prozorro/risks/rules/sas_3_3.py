from datetime import datetime

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.historical_data import get_list_of_cpvs


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-3"
    name = "Закупівля товарів та послуг у одного учасника"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник проводить закупівлі у одного постачальника за 4 "
        "або більше різним кодам предметів закупівлі."
    )
    legitimateness = "Індикатор вводиться для ідентифікації можливої змови замовника та постачальника."
    development_basis = (
        "Цей індикатор було розроблено, оскільки система не зберігає зведену історію закупівель для замовника."
    )
    procurement_methods = ("aboveThresholdUA", "aboveThresholdEU", "aboveThreshold")
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
            active_awards = [award for award in tender.get("awards", []) if award["status"] == "active"]
            # Якщо в процедурі немає жодного об’єкту data.awards, що має статус data.awards.status='active',
            # індикатор приймає значення 0, розрахунок завершується.
            if not active_awards:
                return RiskNotFound()

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
                        procurement_categories=self.procurement_categories,
                    )

                    # За ідентифікатором замовника та ідентифікатором перможця рахуємо коди CPV.
                    # Якщо кількість унікальних предметів закупівлі 4 або більше, індикатор приймає значення 1.
                    if len(result.get("cpv", [])) >= 4:
                        return RiskFound()

                    # Якщо кількість предметів закупівлі дорівнює 3, то перевіряємо, чи входить у список
                    # в рядку поточні коди предметів закупівлі. Якщо хоч один не входить у список,
                    # індикатор приймає значення 1,
                    elif len(result.get("cpv", [])) == 3:
                        classifications = set()
                        for item in tender.get("items", []):
                            if not len(tender.get("lots", [])):
                                classifications.add(item["classification"]["id"])
                            elif item.get("relatedLot") == award.get("lotID"):
                                for lot in tender["lots"]:
                                    if (
                                        lot["status"] not in ("cancelled", "unsuccessful")
                                        and lot["id"] == award["lotID"]
                                    ):
                                        classifications.add(item["classification"]["id"])
                        if len(classifications.difference(set(result["cpv"]))):
                            return RiskFound()
        elif tender.get("status") == self.stop_assessment_status:
            return RiskFromPreviousResult()
        return RiskNotFound()
