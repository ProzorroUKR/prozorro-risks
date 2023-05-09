import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_2 import RiskRule
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
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
    "lot_status,risk_result",
    [
        ("active", RiskFound()),
        ("cancelled", RiskNotFound()),
        ("unsuccessful", RiskNotFound()),
    ],
)
async def test_tender_with_violations_for_different_lot_status(lot_status, risk_result):
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = lot_status
    # 4 bidders
    bid["lotValues"][0]["relatedLot"] = tender["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 3 disqualified award and 1 winner
    disqualified_award["lotID"] = tender["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                winner,
            ],
        }
    )
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


async def test_tender_without_violations():
    # 4 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 2 disqualified award and 1 winner and 1 pending
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    pending_award = deepcopy(disqualified_award)
    pending_award["suppliers"][0]["identifier"]["id"] = "11111111"
    pending_award["status"] = "pending"
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "33333333"

    tender_data.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                pending_award,
                winner,
                disqualified_award_2,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_unique_bidders():
    # 5 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"
    # not unique bidder must not be counted
    bid_5 = deepcopy(bid_4)

    # 3 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender_data.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4, bid_5],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                winner,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_not_unique_awards():
    # 4 bidders
    bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 4 disqualified award and 1 winner
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    # not unique award must not be counted
    disqualified_award_4 = deepcopy(disqualified_award_3)

    tender_data.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                disqualified_award_4,
                winner,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_violations_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 4 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 3 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                winner,
            ],
        }
    )
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
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_without_violations_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 4 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 2 disqualified award and 1 winner and 1 pending
    disqualified_award.pop("lotID", None)
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    pending_award = deepcopy(disqualified_award)
    pending_award["suppliers"][0]["identifier"]["id"] = "11111111"
    pending_award["status"] = "pending"
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "33333333"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                pending_award,
                winner,
                disqualified_award_2,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_unique_bidders_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 5 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"
    # not unique bidder must not be counted
    bid_5 = deepcopy(bid_4)

    # 3 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"

    tender.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4, bid_5],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                winner,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_not_unique_awards_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    # 4 bidders
    bid.pop("lotValues", None)
    bid["status"] = "active"
    bid_2 = deepcopy(bid)
    bid_2["tenderers"][0]["identifier"]["id"] = "11111111"
    bid_3 = deepcopy(bid)
    bid_3["tenderers"][0]["identifier"]["id"] = "22222222"
    bid_4 = deepcopy(bid)
    bid_4["tenderers"][0]["identifier"]["id"] = "33333333"

    # 4 disqualified award and 1 winner
    disqualified_award.pop("lotID", None)
    disqualified_award_1 = deepcopy(disqualified_award)
    disqualified_award_1["suppliers"][0]["identifier"]["id"] = "11111111"
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["suppliers"][0]["identifier"]["id"] = "22222222"
    disqualified_award_3 = deepcopy(disqualified_award)
    disqualified_award_3["suppliers"][0]["identifier"]["id"] = "33333333"
    winner = deepcopy(disqualified_award)
    winner["status"] = "active"
    # not unique award must not be counted
    disqualified_award_4 = deepcopy(disqualified_award_3)

    tender.update(
        {
            "bids": [bid, bid_2, bid_3, bid_4],
            "awards": [
                disqualified_award_1,
                disqualified_award_2,
                disqualified_award_3,
                disqualified_award_4,
                winner,
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "cancelled",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender_data["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_category():
    tender_data.update(
        {
            "mainProcurementCategory": "works",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFromPreviousResult()
