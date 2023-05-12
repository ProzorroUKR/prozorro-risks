import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
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
award_with_complaints["bid_id"] = "f6e09f31d3024049b3bf227742e31bd6"
award_with_complaints["complaints"] = get_fixture_json("complaints")
tender_data["awards"] = [award_with_complaints]


async def test_tender_without_complaints():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("complaints", None)
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_complaints_not_matching_status():
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_active_awards_and_complaint_same_bid_id_without_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
    active_award["bid_id"] = award_with_complaints["bid_id"]
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_active_awards_and_complaint_different_bid_id_without_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
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
async def test_tender_with_active_awards_and_complaint_same_bid_id_with_lots(lot_status, risk_result):
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
    active_award["bid_id"] = award_with_complaints["bid_id"]
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
    active_award["lotID"] = award_with_complaints["lotID"] = tender["lots"][0]["id"]
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_active_awards_and_complaint_different_bid_id_with_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
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
    active_award["lotID"] = award_with_complaints["lotID"] = tender["lots"][0]["id"]
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_active_awards_and_complaint_different_lot_id_with_lots():
    active_award = deepcopy(disqualified_award)
    active_award["status"] = "active"
    active_award["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        },
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a200",
        },
    ]
    award_with_complaints["lotID"] = tender["lots"][0]["id"]
    active_award["lotID"] = tender["lots"][1]["id"]
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
