from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.risk_2_15 import RiskRule
from prozorro.risks.settings import TIMEZONE
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data.update(
    {
        "procurementMethodType": "aboveThresholdUA",
        "status": "active.qualification",
        "mainProcurementCategory": "services",
        "lots": [
            {
                "title": "Бетон та розчин будівельний",
                "status": "active",
                "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
                "date": "2023-02-21T17:36:11.836903+02:00",
                "value": {
                    "amount": 168233.0,
                    "currency": "UAH",
                    "valueAddedTaxIncluded": True,
                },
                "minimalStep": {
                    "amount": 1682.0,
                    "currency": "UAH",
                    "valueAddedTaxIncluded": True,
                },
                "guarantee": {"amount": 0.0, "currency": "UAH"},
            }
        ],
    }
)


async def test_tender_without_active_awards():
    tender_data["awards"][0]["status"] = "pending"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.can_not_be_assessed


async def test_tender_for_4_and_more_cpvs():
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    risk_rule.group_entities_and_suppliers_cpv = AsyncMock(
        return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1", "45310000-5"]}
    )
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_for_3_cpvs_and_no_new_one():
    tender_data["awards"][0]["status"] = "active"
    tender_data["items"][0]["classification"]["id"] = "45310000-2"
    tender_without_lots = deepcopy(tender_data)
    tender_without_lots.pop("lots", None)
    tender_data["items"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    risk_rule = RiskRule()
    risk_rule.group_entities_and_suppliers_cpv = AsyncMock(
        return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1"]}
    )
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found

    indicator_without_lots = await risk_rule.process_tender(tender_without_lots)
    assert indicator_without_lots == RiskIndicatorEnum.risk_not_found


async def test_tender_for_3_cpvs_and_new_one_cpv():
    tender_data["awards"][0]["status"] = "active"
    tender_data["items"][0]["classification"]["id"] = "45310000-4"
    tender_without_lots = deepcopy(tender_data)
    tender_without_lots.pop("lots", None)
    tender_data["items"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    risk_rule = RiskRule()
    risk_rule.group_entities_and_suppliers_cpv = AsyncMock(
        return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1"]}
    )
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_found

    indicator_without_lots = await risk_rule.process_tender(tender_without_lots)
    assert indicator_without_lots == RiskIndicatorEnum.risk_found


async def test_tender_for_less_than_3_cpvs():
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    risk_rule.group_entities_and_suppliers_cpv = AsyncMock(return_value={"cpv": ["45310000-3", "45310000-2"]})
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tenders_with_no_matching_identifiers():
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    risk_rule.group_entities_and_suppliers_cpv = AsyncMock(return_value={})
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "compete",
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_procurement_category():
    tender_data.update(
        {
            "mainProcurementCategory": "works",
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_group_entities_and_suppliers_cpv(db):
    tender_data["dateCreated"] = datetime(2022, 2, 2).isoformat()
    tender_data["procurementMethodType"] = "aboveThresholdUA"
    tender_data["procuringEntityIdentifier"] = "UA-EDR-39604270"
    tender_data["items"][0]["classification"]["id"] = "45310000-4"
    tender_data["contracts"] = [
        {
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
    tender_with_inappropriate_method_type["items"][0]["classification"][
        "id"
    ] = "45310000-3"  # should not appear in result

    tender_with_inappropriate_date = deepcopy(tender_data)
    tender_with_inappropriate_date["dateCreated"] = datetime(2023, 1, 1, tzinfo=TIMEZONE).isoformat()
    tender_with_inappropriate_date["items"][0]["classification"]["id"] = "45310000-5"  # should not appear in result

    tender_with_inappropriate_identifier = deepcopy(tender_data)
    tender_with_inappropriate_identifier["procuringEntityIdentifier"] = "UA-EDR-39604211"
    tender_with_inappropriate_identifier["items"][0]["classification"][
        "id"
    ] = "45310000-6"  # should not appear in result

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

    risk_rule = RiskRule()
    result = await risk_rule.group_entities_and_suppliers_cpv(2022, "UA-EDR-39604270", "UA-EDR", "21809562")
    assert "cpv" in result
    assert sorted(result["cpv"]) == ["45310000-1", "45310000-2", "45310000-4"]
