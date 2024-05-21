from datetime import timedelta

import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.sas24_3_10 import RiskRule
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
tender_data["awards"][0].update({
    "date": (get_now() - timedelta(days=6)).isoformat(),
    "status": "active",
    "bidID": tender_data["bids"][0]["id"],
    "lotID": tender_data["lots"][0]["id"],
})


async def test_open_eu_tender_has_risk():
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_without_lots_has_risk():
    tender = deepcopy(tender_data)
    tender.pop("lots")
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


@pytest.mark.parametrize(
    "amount,category,risk_result",
    [
        (40000, "services", RiskNotFound()),
        (400000, "services", RiskFound()),
        (1600000, "works", RiskFound()),
        (100000, "works", RiskNotFound()),
        (500000, "goods", RiskFound()),
        (20000, "goods", RiskNotFound()),
    ],
)
async def test_tender_value(amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "mainProcurementCategory": category,
        }
    )
    tender["value"]["amount"] = amount
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_bidder_has_no_eligibility_docs():
    tender = deepcopy(tender_data)
    tender["bids"][0].pop("documents")
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskFound()


@pytest.mark.parametrize(
    "doc_date_published,risk_result",
    [
        ((get_now() - timedelta(days=1)).isoformat(), RiskNotFound()),
        (get_now().isoformat(), RiskFound()),
        ((get_now() - timedelta(days=7)).isoformat(), RiskFound()),
    ],
)
async def test_tender_bidder_has_eligibility_docs(doc_date_published, risk_result):
    tender = deepcopy(tender_data)
    tender["bids"][0]["documents"][0]["documentType"] = "eligibilityDocuments"
    tender["bids"][0]["documents"][0]["datePublished"] = doc_date_published
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


@pytest.mark.parametrize(
    "doc_date_published,risk_result",
    [
        ((get_now() - timedelta(days=1)).isoformat(), RiskNotFound()),
        (get_now().isoformat(), RiskFound()),
        ((get_now() - timedelta(days=7)).isoformat(), RiskFound()),
    ],
)
async def test_tender_bidder_has_eligibility_docs_in_another_envelopes(doc_date_published, risk_result):
    tender = deepcopy(tender_data)
    tender["bids"][0]["eligibilityDocuments"] = [tender["bids"][0]["documents"][0]]
    tender["bids"][0].pop("documents")
    tender["bids"][0]["eligibilityDocuments"][0]["documentType"] = "eligibilityDocuments"
    tender["bids"][0]["eligibilityDocuments"][0]["datePublished"] = doc_date_published
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_with_cancelled_award_lot():
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "winner_date,risk_result",
    [
        ((get_now() - timedelta(days=6)).isoformat(), RiskFound()),
        ((get_now() - timedelta(days=2)).isoformat(), RiskNotFound()),
    ],
)
async def test_tender_check_winner_duration(winner_date, risk_result):
    tender = deepcopy(tender_data)
    tender["awards"][0]["date"] = winner_date
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


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
