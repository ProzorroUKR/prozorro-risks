import pytest
from copy import deepcopy
from unittest.mock import patch

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas24_3_4 import RiskRule

from tests.integration.conftest import get_fixture_json

contract_data = get_fixture_json("contract")
tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "social"
tender_data["mainProcurementCategory"] = "works"
tender_data["value"]["amount"] = 1600000


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender", return_value=tender_data)
async def test_tender_without_active_changes_in_contract(mock_tender):
    contract = deepcopy(contract_data)
    contract["changes"][0]["status"] = "pending"
    contract["changes"][1]["status"] = "pending"
    contract["changes"][2]["status"] = "pending"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskNotFound(type="contract", id=contract["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender", return_value=tender_data)
async def test_tender_with_another_rational_types_in_contract(mock_tender):
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = ["volumeCuts"]
    contract["changes"][1]["rationaleTypes"] = ["priceReduction"]
    contract["changes"][2]["rationaleTypes"] = ["itemPriceVariation"]  # only one risked rationalType (we need min two)
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskNotFound(type="contract", id=contract["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender", return_value=tender_data)
async def test_tender_without_changes_in_contract(mock_tender):
    contract = deepcopy(contract_data)
    contract.pop("changes", None)
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskNotFound(type="contract", id=contract["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender", return_value=tender_data)
@pytest.mark.parametrize(
    "rationale_types,risk_result",
    [
        (["itemPriceVariation", "durationExtension"], RiskFound(type="contract", id=contract_data["id"])),
        (["itemPriceVariation", "fiscalYearExtension"], RiskFound(type="contract", id=contract_data["id"])),
        (
            ["itemPriceVariation", "durationExtension", "fiscalYearExtension"],
            RiskFound(type="contract", id=contract_data["id"])
        ),
        (["itemPriceVariation"], RiskNotFound(type="contract", id=contract_data["id"])),
    ],
)
async def test_tender_with_active_changes(mock_tender, rationale_types, risk_result):
    # contract_data has 3 changes which have status active and contain itemPriceVariation in rationaleTypes array
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = rationale_types
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == risk_result


async def test_tender_with_not_risky_contract_status():
    contract = deepcopy(contract_data)
    contract["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskNotFound(type="contract", id=contract["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender")
async def test_tender_with_not_risky_procurement_entity_kind(mock_tender):
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    mock_tender.return_value = tender
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender")
@pytest.mark.parametrize(
    "pmt,risk_result",
    [
        ("belowThreshold", RiskFound(type="contract", id=contract_data["id"])),
        ("negotiation", RiskFound(type="contract", id=contract_data["id"])),
        ("aboveThresholdUA", RiskFound(type="contract", id=contract_data["id"])),
        ("esco", RiskNotFound(type="contract", id=contract_data["id"])),
        ("priceQuotation", RiskNotFound(type="contract", id=contract_data["id"])),
    ],
)
async def test_tender_procurement_method_type(mock_tender, pmt, risk_result):
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = pmt
    mock_tender.return_value = tender
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = ["itemPriceVariation", "durationExtension"]
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == risk_result


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender")
async def test_contract_with_old_tender(mock_tender):
    tender = deepcopy(tender_data)
    tender["dateCreated"] = "2022-12-16T14:30:13.746921+02:00"
    mock_tender.return_value = tender
    risk_rule = RiskRule()
    with pytest.raises(SkipException):
        await risk_rule.process_contract(contract_data)


async def test_contract_with_terminated_status():
    contract = deepcopy(contract_data)
    contract["status"] = "terminated"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskFromPreviousResult(type="contract", id=contract["id"])


@patch("prozorro.risks.rules.sas24_3_4.fetch_tender")
@pytest.mark.parametrize(
    "amount,category,risk_result",
    [
        (1500001, "works", RiskFound(type="contract", id=contract_data["id"])),
        (1600000, "works", RiskFound(type="contract", id=contract_data["id"])),
        (1499999, "works", RiskNotFound(type="contract", id=contract_data["id"])),
        (500000, "works", RiskNotFound(type="contract", id=contract_data["id"])),
        (400001, "services", RiskFound(type="contract", id=contract_data["id"])),
        (1600000, "goods", RiskFound(type="contract", id=contract_data["id"])),
        (399999, "works", RiskNotFound(type="contract", id=contract_data["id"])),
        (20000, "goods", RiskNotFound(type="contract", id=contract_data["id"])),
    ],
)
async def test_contract_with_tender_value(mock_tender, amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    mock_tender.return_value = tender
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = ["itemPriceVariation", "durationExtension"]
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == risk_result
