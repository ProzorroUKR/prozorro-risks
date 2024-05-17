import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_13 import RiskRule
from tests.integration.conftest import get_fixture_json


tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["mainProcurementCategory"] = "works"
tender_data["value"]["amount"] = 1600000
tender_data.update(
    {
        "procurementMethodType": "belowThreshold",
        "status": "active.qualification",
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
tender_data["awards"][0].update({
    "status": "active",
    "bidID": tender_data["bids"][0]["id"],
    "lotID": tender_data["lots"][0]["id"],
    "milestones": [{"code": "24h", "date": "2023-01-01T10:00:03+02:00"}],
})


async def test_tender_with_code_24_has_risk():
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_without_lots_has_risk():
    tender = deepcopy(tender_data)
    tender.pop("lots")
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


@pytest.mark.parametrize(
    "amount,category,risk_rule_class,risk_result",
    [
        (40000, "services", RiskRule, RiskNotFound()),
        (400000, "services", RiskRule, RiskFound()),
        (1600000, "works", RiskRule, RiskFound()),
        (100000, "works", RiskRule, RiskNotFound()),
        (500000, "goods", RiskRule, RiskFound()),
        (20000, "goods", RiskRule, RiskNotFound()),
    ],
)
async def test_tender_value(amount, category, risk_rule_class, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    risk_rule = risk_rule_class()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_awards_does_not_have_milestones():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("milestones")
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_awards_have_milestones_with_another_code():
    tender = deepcopy(tender_data)
    tender["awards"][0]["milestones"][0]["code"] = "alp"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_cancelled_award_lot():
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_tender_status():
    tender = deepcopy(tender_data)
    tender["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "reporting"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()
