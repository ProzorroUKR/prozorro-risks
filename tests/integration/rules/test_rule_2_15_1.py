from copy import deepcopy
from unittest.mock import AsyncMock

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.risk_2_15_1 import RiskRule
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data.update(
    {
        "procurementMethodType": "aboveThresholdUA",
        "status": "active.qualification",
        "mainProcurementCategory": "works",
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
            "mainProcurementCategory": "services",
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found
