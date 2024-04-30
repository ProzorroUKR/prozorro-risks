from datetime import timedelta
from uuid import uuid4

import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_5 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json


tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["mainProcurementCategory"] = "works"
tender_data["value"]["amount"] = 1600000
tender_data.update(
    {
        "procurementMethodType": "aboveThreshold",
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
tender_data["awards"][0]["date"] = (get_now() - timedelta(days=31)).isoformat()

disqualified_award = get_fixture_json("disqualified_award")
disqualified_qualification = get_fixture_json("disqualified_qualification")
disqualified_qualification["lotID"] = tender_data["lots"][0]["id"]
bid = get_fixture_json("bid")
bid["lotValues"][0]["relatedLot"] = tender_data["lots"][0]["id"]
bid["status"] = "active"


async def test_open_eu_tender_has_risk():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    # 2 disqualified bidders on prequalification
    disqualified_qualification_2 = deepcopy(disqualified_qualification)
    disqualified_qualification_2["bidID"] = uuid4().hex
    tender["qualifications"] = [disqualified_qualification, disqualified_qualification_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


async def test_open_eu_tender_without_qualifications():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_open_eu_tender_with_qualification():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    # 1 disqualified bidders on prequalification
    tender["qualifications"] = [disqualified_qualification]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_open_eu_tender_without_winner():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "pending"  # no winner
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    # 2 disqualified bidders on prequalification
    disqualified_qualification_2 = deepcopy(disqualified_qualification)
    disqualified_qualification_2["bidID"] = uuid4().hex
    tender["qualifications"] = [disqualified_qualification, disqualified_qualification_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_open_eu_tender_with_cancelled_lot():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["lots"][0]["status"] = "cancelled"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    # 2 disqualified bidders on prequalification
    disqualified_qualification_2 = deepcopy(disqualified_qualification)
    disqualified_qualification_2["bidID"] = uuid4().hex
    tender["qualifications"] = [disqualified_qualification, disqualified_qualification_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_open_eu_tender_has_second_disqualification_with_milestones():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    # 2 disqualified bidders on prequalification
    disqualified_qualification_2 = deepcopy(disqualified_qualification)
    disqualified_qualification_2["bidID"] = uuid4().hex
    disqualified_qualification_2["milestones"] = [
        {"code": "24h", "date": "2023-01-01T10:00:03+02:00"}
    ]
    tender["qualifications"] = [disqualified_qualification, disqualified_qualification_2]
    risk_rule = RiskRule()
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
async def test_open_eu_tender_value(amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
    # 2 disqualified bidders on prequalification
    disqualified_qualification_2 = deepcopy(disqualified_qualification)
    disqualified_qualification_2["bidID"] = uuid4().hex
    tender["qualifications"] = [disqualified_qualification, disqualified_qualification_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_open_eu_tender_without_lots():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "aboveThresholdEU"
    tender["awards"][0]["status"] = "active"
    tender["awards"][0].pop("lotID", None)
    del tender["lots"]
    # 2 disqualified bidders on prequalification
    disqualified_qualification_1 = deepcopy(disqualified_qualification)
    disqualified_qualification_1.pop("lotID", None)
    disqualified_qualification_2 = deepcopy(disqualified_qualification_1)
    disqualified_qualification_2["bidID"] = uuid4().hex
    tender["qualifications"] = [disqualified_qualification_1, disqualified_qualification_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


@pytest.mark.parametrize(
    "winner_date,risk_result",
    [
        ((get_now() - timedelta(days=6)).isoformat(), RiskFound()),
        ((get_now() - timedelta(days=2)).isoformat(), RiskNotFound()),
    ],
)
async def test_open_tender_has_risk(winner_date, risk_result):
    tender = deepcopy(tender_data)
    tender["awards"][0]["status"] = "active"
    tender["awards"][0]["lotID"] = tender_data["lots"][0]["id"]  # 1 winner
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
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


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
