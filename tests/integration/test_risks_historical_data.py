from copy import deepcopy
from datetime import datetime
from prozorro.risks.historical_data import get_list_of_cpvs
from prozorro.risks.settings import TIMEZONE

from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")


async def test_get_list_of_cpvs(db):
    tender_data["procurementMethodType"] = "aboveThresholdUA"
    tender_data["procuringEntityIdentifier"] = "UA-EDR-39604270"
    tender_data["items"][0]["classification"]["id"] = "45310000-4"
    tender_data["contracts"] = [
        {
            "dateSigned": datetime(2022, 2, 2).isoformat(),
            "status": "active",
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
    tender_2["items"][0]["classification"]["id"] = "45310000-2"
    tender_3 = deepcopy(tender_data)
    tender_3["items"][0]["classification"]["id"] = "45310000-4"
    tender_4 = deepcopy(tender_data)
    tender_4["items"][0]["classification"]["id"] = "45310000-1"

    tender_with_inappropriate_method_type = deepcopy(tender_data)
    tender_with_inappropriate_method_type["procurementMethodType"] = "reporting"
    tender_with_inappropriate_method_type["items"][0]["classification"]["id"] = "45310000-3"  # not appear in result

    tender_with_inappropriate_date = deepcopy(tender_data)
    tender_with_inappropriate_date["contracts"][0]["dateSigned"] = datetime(2023, 1, 1, tzinfo=TIMEZONE).isoformat()
    tender_with_inappropriate_date["items"][0]["classification"]["id"] = "45310000-5"  # should not appear in result

    tender_with_inappropriate_identifier = deepcopy(tender_data)
    tender_with_inappropriate_identifier["procuringEntityIdentifier"] = "UA-EDR-39604211"
    tender_with_inappropriate_identifier["items"][0]["classification"]["id"] = "45310000-6"  # not appear in result

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
        ]
    )

    result = await get_list_of_cpvs(
        year=2022,
        entity_identifier="UA-EDR-39604270",
        supplier_identifier={"scheme": "UA-EDR", "id": "21809562"},
        procurement_methods=("aboveThresholdUA",),
    )
    assert "cpv" in result
    assert sorted(result["cpv"]) == ["45310000-1", "45310000-2", "45310000-4"]
