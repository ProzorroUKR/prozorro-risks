from datetime import datetime

from prozorro.risks.db import aggregate_tenders
from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseRiskRule
from prozorro.risks.settings import TIMEZONE


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

    async def group_entities_and_suppliers_cpv(self, year, entity_identifier, supplier_scheme, supplier_identifier):
        aggregation_pipeline = [
            {
                "$match": {
                    "procuringEntityIdentifier": entity_identifier,
                    "dateCreated": {
                        "$gte": datetime(year, 1, 1, tzinfo=TIMEZONE).isoformat(),
                        "$lt": datetime(year + 1, 1, 1, tzinfo=TIMEZONE).isoformat(),
                    },
                    "procurementMethodType": {"$in": self.procurement_methods},
                    "contracts": {"$exists": True},
                    "contracts.suppliers.identifier.scheme": supplier_scheme,
                    "contracts.suppliers.identifier.id": supplier_identifier,
                }
            },
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": None,
                    "cpv": {"$addToSet": "$items.classification.id"},
                }
            },
            {"$project": {"_id": 0}},
        ]
        return await aggregate_tenders(aggregation_pipeline)

    async def process_tender(self, tender):
        if (
            tender["procurementMethodType"] in self.procurement_methods
            and tender["status"] in self.tender_statuses
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
            and tender.get("mainProcurementCategory") in self.procurement_categories
        ):
            active_awards = [award for award in tender.get("awards", []) if award["status"] == "active"]
            if not active_awards:
                return RiskIndicatorEnum.can_not_be_assessed

            for award in active_awards:
                for supplier in award.get("suppliers", []):
                    supplier_identifier = supplier.get("identifier", {})
                    year = datetime.fromisoformat(tender["dateCreated"]).year
                    result = await self.group_entities_and_suppliers_cpv(
                        year,
                        tender["procuringEntityIdentifier"],
                        supplier_identifier.get("scheme", ""),
                        supplier_identifier.get("id", ""),
                    )
                    if len(result.get("cpv", [])) >= 4:
                        return RiskIndicatorEnum.risk_found

                    # Якщо у рядку кількість предметів закупівлі дорівнює 3, то перевіряємо, чи входить у список
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
