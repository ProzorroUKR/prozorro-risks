from unittest.mock import patch
from uuid import uuid4

import pytest
from copy import deepcopy
from datetime import timedelta

from prozorro.risks.models import RiskNotFound, RiskFound
from prozorro.risks.rules.sas24_3_11_1 import RiskRule
from prozorro.risks.rules.sas24_3_11_2 import RiskRule as RiskRule2
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["mainProcurementCategory"] = "works"
tender_data["value"]["amount"] = 1600000
tender_data.update(
    {
        "procurementMethodType": "reporting",
        "status": "complete",
        "dateCreated": (get_now() + timedelta(days=5)).isoformat(),
    }
)

open_tender_data = deepcopy(tender_data)
open_tender_data.update({
    "procurementMethodType": "aboveThreshold",
    "status": "cancelled",
})
open_tender_data["tenderPeriod"]["startDate"] = get_now().isoformat()
open_tender_data["complaints"] = get_fixture_json("complaints")
open_tender_data["complaints"][0]["status"] = "satisfied"


async def test_tender_with_not_risky_tender_status():
    tender = deepcopy(tender_data)
    tender["status"] = "cancelled"
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "priceQuotation"
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_has_risks(db, api):
    await db.tenders.insert_one(open_tender_data)
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskFound()


@pytest.mark.parametrize(
    "status,risk_rule,risk_result",
    [
        ("active.tendering", RiskRule, RiskNotFound()),
        ("active.tendering", RiskRule2, RiskFound()),
        ("active.qualification", RiskRule, RiskNotFound()),
        ("active.qualification", RiskRule2, RiskFound()),
        ("active.awarded", RiskRule, RiskNotFound()),
        ("active.awarded", RiskRule2, RiskFound()),
        ("cancelled", RiskRule, RiskFound()),
        ("cancelled", RiskRule2, RiskFound()),
    ],
)
async def test_open_tender_status(db, api, status, risk_rule, risk_result):
    open_data = deepcopy(open_tender_data)
    open_data["status"] = status
    await db.tenders.insert_one(open_data)
    risk_rule = risk_rule()
    result = await risk_rule.process_tender(tender_data)
    assert result == risk_result


async def test_tender_has_no_cancelled_open_tenders(db):
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskNotFound()


@pytest.mark.parametrize(
    "not_matched_data",
    [
        ({"status": "complete"}),
        ({"procurementMethodType": "priceQuotation"}),
        ({"title": "Foo bar"}),
    ],
)
async def test_tender_has_open_tenders_with_another_fields(db, api, not_matched_data):
    open_data = deepcopy(open_tender_data)
    open_data.update(not_matched_data)
    await db.tenders.insert_one(open_data)
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskNotFound()


async def test_tender_reporting_has_another_fields(db, api):
    await db.tenders.insert_one(open_tender_data)
    tender = deepcopy(tender_data)
    tender["procuringEntityIdentifier"] = "UA-EDR-22518134"
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()

        tender["procuringEntityIdentifier"] = "UA-EDR-39604270"
        tender["dateCreated"] = (get_now() - timedelta(days=100)).isoformat()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()

        tender["dateCreated"] = open_tender_data["tenderPeriod"]["startDate"]
        tender["subjectOfProcurement"] = "14524"
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()


@pytest.mark.parametrize(
    "tender_date_created,risk_rule,risk_result",
    [
        ((get_now() + timedelta(days=181)).isoformat(), RiskRule, RiskFound()),
        ((get_now() + timedelta(days=180)).isoformat(), RiskRule2, RiskFound()),
        ((get_now() + timedelta(days=181)).isoformat(), RiskRule2, RiskNotFound()),
        ((get_now() + timedelta(days=365)).isoformat(), RiskRule, RiskFound()),
        ((get_now() + timedelta(days=366)).isoformat(), RiskRule, RiskNotFound()),
    ],
)
async def test_tender_reporting_date_ranges(db, api, tender_date_created, risk_rule, risk_result):
    await db.tenders.insert_one(open_tender_data)
    tender = deepcopy(tender_data)
    tender["dateCreated"] = tender_date_created
    risk_rule = risk_rule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


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
async def test_tender_value(db, api, amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    open_data = deepcopy(open_tender_data)
    open_data["value"]["amount"] = amount
    await db.tenders.insert_one(open_data)
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == risk_result


@patch(
    "prozorro.risks.utils.get_object_data",
    return_value=[{"cc": "USD", "rate": 39.5151}, {"cc": "EUR", "rate": 42.3641}],
)
@pytest.mark.parametrize(
    "amount,currency,risk_result",
    [
        (38650, "EUR", RiskFound()),
        (30685, "EUR", RiskNotFound()),
        (44845, "EUR", RiskNotFound()),
        (37000, "USD", RiskFound()),
        (32900, "USD", RiskNotFound()),
        (45550, "USD", RiskNotFound()),
    ],
)
async def test_nbu_exchange(mock_rates, db, api, amount, currency, risk_result):
    open_data = deepcopy(open_tender_data)
    open_data["tenderPeriod"]["startDate"] = "2024-05-01T00:00:00+03:00"
    open_data["value"] = {
        "amount": amount,
        "currency": currency,
    }
    await db.tenders.insert_one(open_data)

    tender = deepcopy(tender_data)
    tender["dateCreated"] = "2024-05-01T01:00:00+03:00"
    for rule_class in (RiskRule, RiskRule2):
        risk_rule = rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == risk_result


async def test_complaints(db, api):
    open_data = deepcopy(open_tender_data)
    del open_data["complaints"]
    await db.tenders.insert_one(open_data)
    risk_rule = RiskRule2()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()

    complaints = deepcopy(get_fixture_json("complaints"))
    complaints[0]["status"] = "satisfied"
    open_data["_id"] = uuid4().hex
    open_data["awards"][0]["complaints"] = complaints
    await db.tenders.insert_one(open_data)
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()
