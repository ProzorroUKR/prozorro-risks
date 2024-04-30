import pytest
from copy import deepcopy

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_4 import RiskRule

from tests.integration.conftest import get_fixture_json

contract_data = get_fixture_json("contract")
tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "social"


async def test_tender_without_active_changes_in_contract():
    contract = deepcopy(contract_data)
    contract["changes"][0]["status"] = "pending"
    contract["changes"][1]["status"] = "pending"
    contract["changes"][2]["status"] = "pending"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract, tender_data)
    assert result == RiskNotFound(type="contract", id=contract["id"])


async def test_tender_with_another_rational_types_in_contract():
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = ["volumeCuts"]
    contract["changes"][1]["rationaleTypes"] = ["priceReduction"]
    contract["changes"][2]["rationaleTypes"] = ["priceReduction"]
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract, tender_data)
    assert result == RiskNotFound(type="contract", id=contract["id"])


async def test_tender_without_changes_in_contract():
    contract = deepcopy(contract_data)
    contract.pop("changes", None)
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract, tender_data)
    assert result == RiskNotFound(type="contract", id=contract["id"])


async def test_tender_with_active_changes():
    # contract_data has 3 changes which have status active and contain itemPriceVariation in rationaleTypes array
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender_data)
    assert result == RiskFound(type="contract", id=contract_data["id"])


async def test_tender_with_not_risky_contract_status():
    contract = deepcopy(contract_data)
    contract["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract)
    assert result == RiskNotFound(type="contract", id=contract["id"])


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender_data)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


async def test_contract_with_old_tender():
    tender = deepcopy(tender_data)
    tender["dateCreated"] = "2022-12-16T14:30:13.746921+02:00"
    risk_rule = RiskRule()
    with pytest.raises(SkipException):
        await risk_rule.process_contract(contract_data, tender)


async def test_contract_with_terminated_status():
    contract_data["status"] = "terminated"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data)
    assert result == RiskFromPreviousResult(type="contract", id=contract_data["id"])
