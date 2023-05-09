from copy import deepcopy
from unittest.mock import patch

import pytest
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_3_1 import RiskRule
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
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


@patch(
    "prozorro.risks.rules.sas_3_3.get_list_of_cpvs",
    return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1", "45310000-5"]},
)
async def test_tender_for_4_and_more_cpvs(mock_cpvs):
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


@patch(
    "prozorro.risks.rules.sas_3_3.get_list_of_cpvs",
    return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1"]},
)
@pytest.mark.parametrize(
    "lot_status,risk_result",
    [
        ("active", RiskFound()),
        ("cancelled", RiskNotFound()),
        ("unsuccessful", RiskNotFound()),
    ],
)
async def test_tender_for_3_and_one_more_cpvs_for_tender_with_lots(mock_cpvs, lot_status, risk_result):
    tender_data["awards"][0]["status"] = "active"
    tender_with_lot = deepcopy(tender_data)
    tender_with_lot["lots"][0]["status"] = lot_status
    tender_with_lot["awards"][0]["lotID"] = tender_with_lot["lots"][0]["id"]
    tender_with_lot["items"][0]["relatedLot"] = tender_with_lot["lots"][0]["id"]
    tender_with_lot["items"][0]["classification"]["id"] = "45310000-5"
    risk_rule = RiskRule()
    assert await risk_rule.process_tender(tender_with_lot) == risk_result


@patch(
    "prozorro.risks.rules.sas_3_3.get_list_of_cpvs", return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1"]}
)
async def test_tender_for_3_cpvs_and_no_new_one(mock_cpvs):
    tender_data["awards"][0]["status"] = "active"
    tender_data["items"][0]["classification"]["id"] = "45310000-2"
    tender_without_lots = deepcopy(tender_data)
    tender_without_lots.pop("lots", None)
    tender_data["items"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()

    result_without_lots = await risk_rule.process_tender(tender_without_lots)
    assert result_without_lots == RiskNotFound()


@patch(
    "prozorro.risks.rules.sas_3_3.get_list_of_cpvs", return_value={"cpv": ["45310000-3", "45310000-2", "45310000-1"]}
)
async def test_tender_for_3_cpvs_and_new_one_cpv(mock_cpvs):
    tender_data["awards"][0]["status"] = "active"
    tender_data["items"][0]["classification"]["id"] = "45310000-4"
    tender_without_lots = deepcopy(tender_data)
    tender_without_lots.pop("lots", None)
    tender_data["items"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()

    result_without_lots = await risk_rule.process_tender(tender_without_lots)
    assert result_without_lots == RiskFound()


@patch("prozorro.risks.rules.sas_3_3.get_list_of_cpvs", return_value={"cpv": ["45310000-3", "45310000-2"]})
async def test_tender_for_less_than_3_cpvs(mock_cpvs):
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


@patch("prozorro.risks.rules.sas_3_3.get_list_of_cpvs", return_value={})
async def test_tenders_with_no_matching_identifiers(mock_cpvs):
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "cancelled",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_category():
    tender_data.update(
        {
            "mainProcurementCategory": "services",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFromPreviousResult()
