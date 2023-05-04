import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_8 import RiskRule
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
award["bid_id"] = "f6e09f31d3024049b3bf227742e31bd6"
award_2 = deepcopy(disqualified_award)
award_2["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
tender_data["awards"] = [award, award_2]


async def test_tender_without_complaints():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("complaints", None)
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_complaints_not_matching_status():
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_without_milestones():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("milestones", None)
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_milestones_not_matching_code():
    milestone = {"code": "test", "date": "2023-01-01T00:00:03+02:00"}
    tender = deepcopy(tender_data)
    tender["awards"][0]["milestones"] = [milestone]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_milestone_date_more_than_complaint_date_for_same_award():
    tender = deepcopy(tender_data)
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    tender["awards"][0]["complaints"][0]["dateDecision"] = "2023-01-01T12:00:03+02:00"
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][0]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_award_for_same_bidder_without_milestones_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender["awards"][1]["bid_id"] = tender["awards"][0]["bid_id"]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_milestone_date_more_than_complaint_date_for_same_bidder_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender["awards"][0]["complaints"][0]["date"] = "2023-01-01T12:00:03+02:00"
    tender["awards"][1]["bid_id"] = tender["awards"][0]["bid_id"]
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][1]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_milestone_date_more_than_complaint_date_for_another_bidder_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender["awards"][0]["complaints"][0]["date"] = "2023-01-01T12:00:03+02:00"
    tender["awards"][1]["bid_id"] = "f6e09f31d3024049b3bf227742e31b00"
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][1]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_award_for_same_bidder_without_milestones_with_lots():
    tender = deepcopy(tender_data)
    tender["awards"][0]["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    tender["awards"][1]["bid_id"] = tender["awards"][0]["bid_id"]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "lot_status,risk_result",
    [
        ("active", RiskFound()),
        ("cancelled", RiskNotFound()),
        ("unsuccessful", RiskNotFound()),
    ],
)
async def test_tender_with_milestone_date_more_than_complaint_date_for_same_bidder_with_lots(lot_status, risk_result):
    tender = deepcopy(tender_data)
    tender["awards"][0]["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": lot_status,
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    tender["awards"][0]["complaints"][0]["date"] = "2023-01-01T12:00:03+02:00"
    tender["awards"][1]["bid_id"] = tender["awards"][0]["bid_id"]
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][1]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


@pytest.mark.parametrize(
    "lot_status,risk_result",
    [
        ("active", RiskNotFound()),
        ("cancelled", RiskNotFound()),
        ("unsuccessful", RiskNotFound()),
    ],
)
async def test_tender_with_milestone_date_more_than_complaint_date_for_another_bidder_with_lots(
    lot_status, risk_result
):
    tender = deepcopy(tender_data)
    tender["awards"][0]["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": lot_status,
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    tender["awards"][0]["complaints"][0]["date"] = "2023-01-01T12:00:03+02:00"
    tender["awards"][1]["bid_id"] = "f6e09f31d3024049b3bf227742e31b00"
    milestone_1 = {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-02T10:00:03+02:00"}
    tender["awards"][1]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_milestone_date_less_than_complaint_date_decision():
    tender = deepcopy(tender_data)
    tender["awards"][0]["complaints"][0]["dateDecision"] = "2023-01-10T12:00:03+02:00"
    milestone_1 = {"code": "24h", "date": "2023-01-09T10:00:03+02:00"}
    milestone_2 = {"code": "24h", "date": "2023-01-08T05:00:03+02:00"}
    tender["awards"][0]["milestones"] = [milestone_1, milestone_2]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "cancelled",
        }
    )
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFromPreviousResult()
