from copy import deepcopy

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.contracts.risk_3_4 import RiskRule

from tests.integration.conftest import get_fixture_json

contract_data = get_fixture_json("contract")


async def test_tender_without_active_changes_in_contract():
    contract = deepcopy(contract_data)
    contract["changes"][0]["status"] = "pending"
    contract["changes"][1]["status"] = "pending"
    contract["changes"][2]["status"] = "pending"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_another_rational_types_in_contract():
    contract = deepcopy(contract_data)
    contract["changes"][0]["rationaleTypes"] = ["volumeCuts"]
    contract["changes"][1]["rationaleTypes"] = ["priceReduction"]
    contract["changes"][2]["rationaleTypes"] = ["priceReduction"]
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_without_changes_in_contract():
    contract = deepcopy(contract_data)
    contract.pop("changes", None)
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_more_than_90_days_between_date_signed_changes():
    contract = deepcopy(contract_data)
    contract["changes"][0]["dateSigned"] = "2019-01-01T16:39:01.640632+02:00"
    contract["changes"][1]["dateSigned"] = "2019-05-01T16:39:01.640632+02:00"
    contract["changes"][2]["dateSigned"] = "2019-10-01T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_less_than_90_days_between_date_signed_changes():
    contract = deepcopy(contract_data)
    contract["changes"][0]["dateSigned"] = "2019-01-01T16:39:01.640632+02:00"
    contract["changes"][1]["dateSigned"] = "2019-02-01T16:39:01.640632+02:00"
    contract["changes"][2]["dateSigned"] = "2019-03-01T16:39:01.640632+02:00"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_with_not_risky_contract_status():
    contract = deepcopy(contract_data)
    contract["status"] = "terminated"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(contract)
    assert indicator == RiskIndicatorEnum.risk_not_found
