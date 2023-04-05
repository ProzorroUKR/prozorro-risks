from copy import deepcopy

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.risk_3_8 import RiskRule
from tests.integration.conftest import get_fixture_json


risk_rule = RiskRule()
tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data.update(
    {
        "procurementMethodType": "aboveThreshold",
        "status": "active.qualification",
    }
)
disqualified_award = get_fixture_json("disqualified_award")
award = deepcopy(disqualified_award)
award["complaints"] = get_fixture_json("complaints")
tender_data["awards"] = [award]


async def test_tender_without_complaints():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("complaints", None)
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_complaints_not_matching_status():
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_without_milestones():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("milestones", None)
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_milestones_not_matching_code():
    milestone = {"code": "test", "date": "2023-01-01T00:00:03+02:00"}
    tender = deepcopy(tender_data)
    tender["awards"][0]["milestones"] = [milestone]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_milestone_date_more_than_complaint_date_decision():
    tender = deepcopy(tender_data)
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    tender["awards"][0]["complaints"][0]["dateDecision"] = "2023-01-01T12:00:03+02:00"
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][0]["milestones"] = [milestone_1, milestone_2]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_with_milestone_date_less_than_complaint_date_decision():
    tender = deepcopy(tender_data)
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    tender["awards"][0]["complaints"][0]["dateDecision"] = "2023-01-10T12:00:03+02:00"
    milestone_1 = {"code": "24h", "date": "2023-01-09T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-08T05:00:03+02:00"}
    tender["awards"][0]["milestones"] = [milestone_1, milestone_2]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "compete",
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
