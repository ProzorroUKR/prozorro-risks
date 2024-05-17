from datetime import timedelta

import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_15 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["mainProcurementCategory"] = "services"
tender_data["value"]["amount"] = 500000
tender_data.update(
    {
        "procurementMethodType": "aboveThresholdUA",
        "status": "active.qualification",
        "mainProcurementCategory": "services",
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

disqualified_award = get_fixture_json("disqualified_award")
bid = get_fixture_json("bid")


async def test_tender_without_winner():
    tender_data["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["status"] = "pending"
    tender_data["awards"].append(disqualified_award)
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_without_disqualified_award():
    tender_data["awards"] = [tender_data["awards"][0]]
    tender_data["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "lot_status,winner_date,risk_result",
    [
        ("cancelled", (get_now() - timedelta(days=6)).isoformat(), RiskNotFound()),
        ("unsuccessful", (get_now() - timedelta(days=6)).isoformat(), RiskNotFound()),
        ("active", (get_now() - timedelta(days=6)).isoformat(), RiskFound()),
        ("active", (get_now() - timedelta(days=2)).isoformat(), RiskNotFound()),
    ],
)
async def test_tender_with_violations_for_different_lot_status(lot_status, winner_date, risk_result):
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = lot_status
    # 3 bidders
    bid["lotValues"][0]["relatedLot"] = tender["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award["lotID"] = tender["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    winner["date"] = winner_date

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                winner,
            ],
        }
    )
    tender["awards"][0]["complaints"] = get_fixture_json("complaints")
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_less_than_2_disqualified_awards():
    # 2 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"

    # 1 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender_data.update({"bids": [bid, bid_2], "awards": [disqualified_award_1, winner]})
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_without_award_complaint():
    tender = deepcopy(tender_data)
    # 3 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "33333333"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                winner,
                disqualified_award_2,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_award_complaint_in_another_status():
    tender = deepcopy(tender_data)
    # 3 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "33333333"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                winner,
                disqualified_award_2,
            ],
        }
    )
    tender["awards"][0]["complaints"] = get_fixture_json("complaints")
    tender["awards"][0]["complaints"][0]["status"] = "satisfied"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "amount,category,risk_rule_class,risk_result",
    [
        (400000, "services", RiskRule, RiskFound()),
        (40000, "services", RiskRule, RiskNotFound()),
        (1500000, "works", RiskRule, RiskFound()),
        (1499999, "works", RiskRule, RiskNotFound()),
        (500000, "goods", RiskRule, RiskFound()),
        (20000, "goods", RiskRule, RiskNotFound()),
    ],
)
async def test_tender_value(amount, category, risk_rule_class, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    # 3 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                winner,
            ],
        }
    )
    tender["awards"][0]["complaints"] = get_fixture_json("complaints")
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    risk_rule = risk_rule_class()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_violations_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 3 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                winner,
            ],
        }
    )
    tender["awards"][0]["complaints"] = get_fixture_json("complaints")
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_less_than_2_disqualified_awards_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 2 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"

    # 1 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update({"bids": [bid, bid_2], "awards": [disqualified_award_1, winner]})
    tender["awards"][0]["complaints"] = get_fixture_json("complaints")
    tender["awards"][0]["complaints"][0]["status"] = "resolved"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_without_violations_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 3 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"

    # 2 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "33333333"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3],
            "awards": [
                disqualified_award_1,
                winner,
                disqualified_award_2,
            ],
        }
    )
    # awards don't have complaints
    tender["awards"][0].pop("complaints", None)
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
