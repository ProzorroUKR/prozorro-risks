import pytest
from copy import deepcopy

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_7 import RiskRule

from tests.integration.conftest import get_fixture_json

contract_data = get_fixture_json("contract")
contract_data["status"] = "active"
tender_data = get_fixture_json("base_tender")
tender_data["contracts"] = [contract_data]
tender_data["procuringEntity"]["kind"] = "general"
tender_data["value"]["amount"] = 1600000
tender_data.update(
    {
        "procurementMethodType": "aboveThresholdUA",
        "mainProcurementCategory": "works",
    }
)


async def test_tender_contract_date_and_contract_terminated_date_differ_for_less_than_60_days():
    tender_data["contracts"][0]["date"] = "2019-01-01T16:39:01.640632+02:00"
    contract_data["period"]["endDate"] = "2019-01-10T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender_data)
    assert result == RiskFound(type="contract", id=contract_data["id"])


async def test_tender_contract_date_and_contract_terminated_date_differ_for_more_than_60_days():
    tender_data["contracts"][0]["date"] = "2019-01-01T16:39:01.640632+02:00"
    contract_data["period"]["endDate"] = "2019-03-10T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender_data)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


async def test_tender_with_not_risky_contract_status():
    contract = deepcopy(contract_data)
    contract["status"] = "pending"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract, tender_data)
    assert result == RiskNotFound(type="contract", id=contract["id"])


async def test_tender_with_not_risky_procurement_type():
    tender = deepcopy(tender_data)
    tender.update({"procurementMethodType": "esco"})
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


async def test_tender_with_not_risky_procurement_category():
    tender = deepcopy(tender_data)
    tender.update({"mainProcurementCategory": "services"})
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender)
    assert result == RiskNotFound(type="contract", id=contract_data["id"])


async def test_contract_with_old_tender():
    tender = deepcopy(tender_data)
    tender["dateCreated"] = "2022-12-16T14:30:13.746921+02:00"
    risk_rule = RiskRule()
    with pytest.raises(SkipException):
        await risk_rule.process_contract(contract_data, tender)


@pytest.mark.parametrize(
    "amount,risk_result",
    [
        (1500000, RiskFound(type="contract", id=contract_data["id"])),
        (1600000, RiskFound(type="contract", id=contract_data["id"])),
        (1499999, RiskNotFound(type="contract", id=contract_data["id"])),
        (500000, RiskNotFound(type="contract", id=contract_data["id"])),
    ],
)
async def test_contract_with_tender_value(amount, risk_result):
    tender = deepcopy(tender_data)
    tender["value"]["amount"] = amount
    tender["contracts"][0]["date"] = "2019-01-01T16:39:01.640632+02:00"
    contract_data["period"]["endDate"] = "2019-01-10T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    result = await risk_rule.process_contract(contract_data, tender)
    assert result == risk_result
