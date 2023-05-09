from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas_2_16 import RiskRule

from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")


async def test_tender_with_award_complaints():
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.qualification",
        }
    )
    tender_data["awards"][0]["complaints"] = [{"test": "test_complaint"}]
    risk_rule = RiskRule()
    result = risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_cancelled_award():
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.qualification",
        }
    )
    tender_data["awards"][0].pop("complaints", None)
    tender_data["awards"][0]["status"] = "cancelled"
    risk_rule = RiskRule()
    result = risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_pending_award():
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.qualification",
        }
    )
    tender_data["awards"][0].pop("complaints", None)
    tender_data["awards"][0]["status"] = "pending"
    risk_rule = RiskRule()
    result = risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    risk_rule = RiskRule()
    result = risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_categories():
    tender_data.update(
        {
            "status": "active.tendering",
        }
    )
    risk_rule = RiskRule()
    result = risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()
