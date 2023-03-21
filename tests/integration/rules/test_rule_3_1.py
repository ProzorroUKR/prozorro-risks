from datetime import timedelta

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.risk_3_1 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
complaints = get_fixture_json("complaints")


async def test_tender_with_satisfied_complaints_more_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_with_satisfied_complaints_less_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=10)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_satisfied_award_complaints_more_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    tender_data["awards"][0]["complaints"] = complaints
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_with_satisfied_award_complaints_less_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=10)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    tender_data["awards"][0]["complaints"] = complaints
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_without_satisfied_complaints():
    tender_data.pop("complaints", None)
    tender_data["awards"][0].pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    risk_rule = RiskRule()
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.can_not_be_assessed


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
