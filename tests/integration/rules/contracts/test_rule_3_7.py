from copy import deepcopy
from unittest.mock import patch

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.contracts.risk_3_7 import RiskRule

from tests.integration.conftest import get_fixture_json

contract_data = get_fixture_json("contract")
contract_data["status"] = "terminated"
tender_data = get_fixture_json("base_tender")
tender_data["contracts"] = [contract_data]
tender_data["procuringEntity"]["kind"] = "general"
tender_data.update(
    {
        "procurementMethodType": "aboveThresholdUA",
        "mainProcurementCategory": "works",
    }
)


@patch("prozorro.risks.rules.contracts.risk_3_7.fetch_tender")
async def test_tender_contract_date_and_contract_terminated_date_differ_for_less_than_60_days(mock_tender):
    tender_data["contracts"][0]["date"] = "2019-01-01T16:39:01.640632+02:00"
    mock_tender.return_value = tender_data
    contract_data["dateModified"] = "2019-01-10T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract_data)
    assert indicator == RiskIndicatorEnum.risk_found


@patch("prozorro.risks.rules.contracts.risk_3_7.fetch_tender")
async def test_tender_contract_date_and_contract_terminated_date_differ_for_more_than_60_days(mock_tender):
    tender_data["contracts"][0]["date"] = "2019-01-01T16:39:01.640632+02:00"
    mock_tender.return_value = tender_data
    contract_data["dateModified"] = "2019-03-10T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_contract_status():
    contract = deepcopy(contract_data)
    contract["status"] = "active"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found


@patch("prozorro.risks.rules.contracts.risk_3_7.fetch_tender")
async def test_tender_with_not_risky_procurement_type(mock_tender):
    tender_data.update({"procurementMethodType": "reporting"})
    mock_tender.return_value = tender_data
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


@patch("prozorro.risks.rules.contracts.risk_3_7.fetch_tender")
async def test_tender_with_not_risky_procurement_entity_kind(mock_tender):
    tender_data["procuringEntity"]["kind"] = "other"
    mock_tender.return_value = tender_data
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


@patch("prozorro.risks.rules.contracts.risk_3_7.fetch_tender")
async def test_tender_with_not_risky_procurement_category(mock_tender):
    tender_data.update({"mainProcurementCategory": "services"})
    mock_tender.return_value = tender_data
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found
