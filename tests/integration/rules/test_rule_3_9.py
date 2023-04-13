import pytest
from copy import deepcopy

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.sas_3_9 import RiskRule
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
award_with_complaints = deepcopy(disqualified_award)
award_with_complaints["complaints"] = get_fixture_json("complaints")
tender_data["awards"] = [award_with_complaints]


async def test_tender_without_complaints():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("complaints", None)
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_complaints_not_matching_status():
    indicator = await risk_rule.process_tender(tender_data)
    assert indicator == RiskIndicatorEnum.risk_not_found


async def test_tender_with_active_awards_and_complaint_same_bid_id_without_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["bid_id"] = award_with_complaints["complaints"][0]["bid_id"]
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    indicator = await risk_rule.process_tender(tender)
    assert indicator == RiskIndicatorEnum.risk_found


async def test_tender_with_active_awards_and_complaint_different_bid_id_without_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
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
async def test_tender_with_active_awards_and_complaint_same_bid_id_with_lots(lot_status, risk_indicator):
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["bid_id"] = award_with_complaints["complaints"][0]["bid_id"]
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": lot_status,
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    indicator = await risk_rule.process_tender(tender)
    assert indicator == risk_indicator


async def test_tender_with_active_awards_and_complaint_different_bid_id_with_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    indicator = await risk_rule.process_tender(tender)
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
