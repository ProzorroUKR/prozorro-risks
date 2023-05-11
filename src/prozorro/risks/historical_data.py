from datetime import datetime

from prozorro.risks.db import aggregate_tenders
from prozorro.risks.settings import TIMEZONE


async def get_list_of_cpvs(
    *_,
    year=None,
    entity_identifier=None,
    procurement_methods=None,
    supplier_identifier=None,
    procurement_categories=None
):
    """
    Get list of unique CPVs for provided filters arguments.
    :param _:
    :param year: int Year of tender dateCreated
    :param entity_identifier: str Procuring entity identifier scheme + id ("UA-EDR-39604270")
    :param procurement_methods: tuple Available procuring method types
    :param supplier_identifier: dict Contract supplier identifier ({"scheme": "UA-EDR", "id": "45310000-7"})
    :param procurement_categories: tuple Available procurement categories
    :return: dict List of CPVs ({"cpv": [...]})
    """
    filters = {
        "procuringEntityIdentifier": entity_identifier,  # first field from compound_procuring_entity_index
        "contracts.dateSigned": {  # second field from compound_procuring_entity_index
            "$gte": datetime(year, 1, 1, tzinfo=TIMEZONE).isoformat(),
            "$lt": datetime(year + 1, 1, 1, tzinfo=TIMEZONE).isoformat(),
        },
    }
    if procurement_methods:
        filters["procurementMethodType"] = {"$in": procurement_methods}
    if procurement_categories:
        filters["mainProcurementCategory"] = {"$in": procurement_categories}
    if supplier_identifier:
        filters.update(
            {
                "contracts.suppliers.identifier.scheme": supplier_identifier.get("scheme", ""),
                "contracts.suppliers.identifier.id": supplier_identifier.get("id", ""),
            }
        )
    aggregation_pipeline = [
        {"$match": filters},
        {"$unwind": "$contracts"},
        {
            "$match": {
                "contracts.dateSigned": {
                    "$gte": datetime(year, 1, 1, tzinfo=TIMEZONE).isoformat(),
                    "$lt": datetime(year + 1, 1, 1, tzinfo=TIMEZONE).isoformat(),
                }
            }
        },
        {"$unwind": "$contracts.items"},
        {
            "$group": {
                "_id": None,
                "cpv": {"$addToSet": "$contracts.items.classification.id"},
            }
        },
        {"$project": {"_id": 0}},
    ]
    return await aggregate_tenders(aggregation_pipeline)
