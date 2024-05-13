from datetime import timedelta

import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_9 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json


risk_rule = RiskRule()
tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["value"]["amount"] = 1600000
tender_data.update(
    {
        "procurementMethodType": "aboveThreshold",
        "status": "active.qualification",
        "mainProcurementCategory": "works",
    }
)

disqualified_award = get_fixture_json("disqualified_award")
award_with_complaints = deepcopy(disqualified_award)
award_with_complaints["bid_id"] = "f6e09f31d3024049b3bf227742e31bd6"
award_with_complaints["complaints"] = get_fixture_json("complaints")
award_with_complaints["complaints"][0]["status"] = "satisfied"
tender_data["awards"] = [award_with_complaints]

active_award_data = deepcopy(disqualified_award)
active_award_data["status"] = "active"
active_award_data["id"] = "f2588db5ac4b4fe0a3628fcb1b5fda75"
active_award_data["date"] = (get_now() - timedelta(days=31)).isoformat()


async def test_tender_without_complaints():
    tender = deepcopy(tender_data)
    tender["awards"][0].pop("complaints", None)
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_complaints_not_matching_status():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "declined"
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_active_awards_and_complaint_same_bid_id_in_resolved_status():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_active_awards_and_complaint_same_bid_id_without_lots():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_active_awards_and_complaint_different_bid_id_without_lots():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
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
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
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


async def test_tender_with_active_awards_and_complaint_same_bid_id_with_lots_short_winner_date():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    active_award["date"] = (get_now() - timedelta(days=5)).isoformat()
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
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


@pytest.mark.parametrize(
    "amount,category,risk_result",
    [
        (1500000, "works", RiskFound()),
        (1600000, "works", RiskFound()),
        (1499999, "works", RiskNotFound()),
        (500000, "works", RiskNotFound()),
        (400000, "services", RiskFound()),
        (1600000, "goods", RiskFound()),
        (399999, "works", RiskNotFound()),
        (20000, "goods", RiskNotFound()),
    ],
)
async def test_tender_value(amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = award_with_complaints["bid_id"]
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender["awards"] = [award_with_complaints, active_award]
    tender["lots"] = [
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a295",
        }
    ]
    active_award["lotID"] = award_with_complaints["lotID"] = tender["lots"][0]["id"]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_active_awards_and_complaint_different_bid_id_with_lots():
    active_award = deepcopy(active_award_data)
    active_award["bid_id"] = "e1cb6a5520984996a0d99c83aa93cd10"  # another bidder
    award_with_complaints["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a295"
    tender = deepcopy(tender_data)
    tender["awards"] = [award_with_complaints, active_award]
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
