from copy import deepcopy
from datetime import datetime
from prozorro.risks.historical_data import get_list_of_cpvs
from prozorro.risks.settings import TIMEZONE

from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")


async def test_get_list_of_cpvs(db):
    tender_data["procurementMethodType"] = "aboveThresholdUA"
    tender_data["procuringEntityIdentifier"] = "UA-EDR-39604270"
    tender_data["mainProcurementCategory"] = "works"
    tender_data["contracts"] = [
        {
            "dateSigned": datetime(2022, 2, 2).isoformat(),
            "status": "active",
            "items": [{"classification": {"id": "45310000-4"}}],
            "suppliers": [
                {
                    "contactPoint": {
                        "telephone": "+380669727047",
                        "name": "Александр Гамаза",
                        "email": "edelveys.stb@ukr.net",
                    },
                    "identifier": {
                        "scheme": "UA-EDR",
                        "id": "21809562",
                        "legalName": 'ТОВ "ТК ЕДЕЛЬВЕЙС"',
                    },
                    "name": 'ТОВ "ТК ЕДЕЛЬВЕЙС"',
                }
            ],
        }
    ]
    tender_2 = deepcopy(tender_data)
    tender_2["contracts"][0]["items"][0]["classification"]["id"] = "45310000-2"
    tender_3 = deepcopy(tender_data)
    tender_3["contracts"][0]["items"][0]["classification"]["id"] = "45310000-4"
    tender_4 = deepcopy(tender_data)
    tender_4["contracts"][0]["items"][0]["classification"]["id"] = "45310000-1"
    # add one more contracts without dateSigned
    tender_4["contracts"].append(
        {
            "status": "pending",
            "items": [{"classification": {"id": "45310000-7"}}],
            "suppliers": [
                {
                    "contactPoint": {
                        "telephone": "+380669727047",
                        "name": "Александр Гамаза",
                        "email": "edelveys.stb@ukr.net",
                    },
                    "identifier": {
                        "scheme": "UA-EDR",
                        "id": "21809562",
                        "legalName": 'ТОВ "ТК ЕДЕЛЬВЕЙС"',
                    },
                    "name": 'ТОВ "ТК ЕДЕЛЬВЕЙС"',
                }
            ],
        }
    )

    tender_with_inappropriate_method_type = deepcopy(tender_data)
    tender_with_inappropriate_method_type["procurementMethodType"] = "reporting"
    tender_with_inappropriate_method_type["contracts"][0]["items"][0]["classification"][
        "id"
    ] = "45310000-3"  # not appear in result

    tender_with_inappropriate_date = deepcopy(tender_data)
    tender_with_inappropriate_date["contracts"][0]["dateSigned"] = datetime(2023, 1, 1, tzinfo=TIMEZONE).isoformat()
    tender_with_inappropriate_date["contracts"][0]["items"][0]["classification"][
        "id"
    ] = "45310000-5"  # should not appear in result

    tender_with_inappropriate_identifier = deepcopy(tender_data)
    tender_with_inappropriate_identifier["procuringEntityIdentifier"] = "UA-EDR-39604211"
    tender_with_inappropriate_identifier["contracts"][0]["items"][0]["classification"][
        "id"
    ] = "45310000-6"  # not appear in result

    tender_with_inappropriate_category = deepcopy(tender_data)
    tender_with_inappropriate_category["mainProcurementCategory"] = "goods"
    tender_with_inappropriate_category["contracts"][0]["items"][0]["classification"][
        "id"
    ] = "45310000-8"  # not appear in result

    tender_without_contracts = deepcopy(tender_data)
    tender_without_contracts.pop("contracts", None)
    tender_without_contracts["items"][0]["classification"]["id"] = "45310000-7"  # should not appear in result

    await db.tenders.insert_many(
        [
            tender_data,
            tender_2,
            tender_3,
            tender_4,
            tender_with_inappropriate_method_type,
            tender_with_inappropriate_date,
            tender_with_inappropriate_identifier,
            tender_without_contracts,
            tender_with_inappropriate_category,
        ]
    )

    result = await get_list_of_cpvs(
        year=2022,
        entity_identifier="UA-EDR-39604270",
        supplier_identifier={"scheme": "UA-EDR", "id": "21809562"},
        procurement_methods=("aboveThresholdUA",),
        procurement_categories=("works",),
    )
    assert "cpv" in result
    assert sorted(result["cpv"]) == ["45310000-1", "45310000-2", "45310000-4"]
