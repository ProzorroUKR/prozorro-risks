import pytest
from copy import deepcopy

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.sas_3_6 import RiskRule
from tests.integration.conftest import get_fixture_json


risk_rule = RiskRule()
tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data.update(
    {
        "procurementMethodType": "aboveThreshold",
        "status": "active.qualification",
        "lots": [
            {
                "title": "Бетон та розчин будівельний",
                "status": "active",
                "id": "c2bb6ff3e8e547bee11d8bff23e8a290",
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

disqualified_award = get_fixture_json("disqualified_award")
award = deepcopy(disqualified_award)
award["status"] = "active"


async def test_tender_without_lots_with_big_difference_in_amounts():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender["value"]["amount"] = 1000
    award["value"]["amount"] = 700
    tender["awards"] = [award]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_without_lots_with_difference_in_amounts_less_than_30_percents():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender["value"]["amount"] = 1000
    award["value"]["amount"] = 900
    tender["awards"] = [award]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


@pytest.mark.parametrize(
    "lot_status,risk_indicator",
    [
        ("active", RiskIndicatorEnum.risk_found),
        ("cancelled", RiskIndicatorEnum.risk_not_found),
        ("unsuccessful", RiskIndicatorEnum.risk_not_found),
    ],
)
async def test_tender_with_big_difference_in_lot_and_award_amounts(lot_status, risk_indicator):
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = lot_status
    tender["lots"][0]["value"]["amount"] = 1000
    award["lotID"] = tender["lots"][0]["id"]
    award["value"]["amount"] = 700
    tender["awards"] = [award]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == risk_indicator


async def test_tender_with_difference_in_lot_and_award_amounts_less_than_30_percents():
    tender = deepcopy(tender_data)
    tender["lots"][0]["value"]["amount"] = 1000
    award["lotID"] = tender["lots"][0]
    award["value"]["amount"] = 900
    tender["awards"] = [award]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_lots_not_matched_awards():
    tender_data["awards"] = [award]
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "cancelled",
        }
    )
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.use_previous_result
