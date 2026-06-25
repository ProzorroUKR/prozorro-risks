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
        "causeDetails": {"code": "openUnsuccessful", "scheme": "DECREE1178"},
    }
)

open_tender_data = deepcopy(tender_data)
open_tender_data.pop("causeDetails", None)
open_tender_data.update(
    {
        "procurementMethodType": "aboveThreshold",
        "status": "cancelled",
    }
)
open_tender_data["tenderPeriod"]["startDate"] = get_now().isoformat()
open_tender_data["complaints"] = get_fixture_json("complaints")
open_tender_data["complaints"][0]["status"] = "satisfied"


# ---------------------------------------------------------------------------
# Shared gating: neither rule fires when the basic requirements are not met.
# ---------------------------------------------------------------------------
async def test_tender_with_not_risky_tender_status():
    tender = deepcopy(tender_data)
    tender["status"] = "cancelled"
    for rule_class in (RiskRule, RiskRule2):
        result = await rule_class().process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "priceQuotation"
    for rule_class in (RiskRule, RiskRule2):
        result = await rule_class().process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    for rule_class in (RiskRule, RiskRule2):
        result = await rule_class().process_tender(tender)
        assert result == RiskNotFound()


async def test_tender_older_than_180_days_returns_no_risk(db, api):
    await db.tenders.insert_one(open_tender_data)
    tender = deepcopy(tender_data)
    tender["dateCreated"] = (get_now() - timedelta(days=181)).isoformat()
    for rule_class in (RiskRule, RiskRule2):
        result = await rule_class().process_tender(tender)
        assert result == RiskNotFound()


async def test_sas24_no_cause_no_risk(db):
    # Причина не обрана взагалі -> ризик не спрацьовує (навіть без відмінених відкритих торгів).
    tender = deepcopy(tender_data)
    tender.pop("causeDetails", None)
    assert await RiskRule().process_tender(tender) == RiskNotFound()


async def test_sas24_null_cause_no_risk(db):
    tender = deepcopy(tender_data)
    tender["causeDetails"] = None
    assert await RiskRule().process_tender(tender) == RiskNotFound()


@pytest.mark.parametrize("code", ["marketUnsuccessful", "defencePurchase", "quick"])
async def test_sas24_other_cause_no_risk(db, code):
    # Обрана будь-яка інша причина (не openUnsuccessful) -> ризик не спрацьовує.
    tender = deepcopy(tender_data)
    tender["causeDetails"] = {"code": code, "scheme": "DECREE1178"}
    assert await RiskRule().process_tender(tender) == RiskNotFound()


async def test_sas24_matching_cancelled_open_tender_no_risk(db, api):
    # Протягом року були відмінені відкриті торги з цієї причини -> ризик не спрацьовує.
    await db.tenders.insert_one(open_tender_data)
    assert await RiskRule().process_tender(tender_data) == RiskNotFound()


async def test_sas24_cancelled_open_tender_value_out_of_range_has_risk(db, api):
    # Відмінені відкриті торги є, але value поза межами +-10% -> не зараховуються -> ризик.
    open_data = deepcopy(open_tender_data)
    open_data["value"] = {"amount": tender_data["value"]["amount"] * 2, "currency": "UAH"}
    await db.tenders.insert_one(open_data)
    assert await RiskRule().process_tender(tender_data) == RiskFound()


async def test_sas24_one_of_two_open_tenders_matches_value_no_risk(db, api):
    # Достатньо однієї відміненої закупівлі з відповідним value, щоб ризик не спрацював.
    open_data_1 = deepcopy(open_tender_data)
    open_data_2 = deepcopy(open_tender_data)
    open_data_2["_id"] = uuid4().hex
    open_data_2["id"] = uuid4().hex
    open_data_2["value"] = {"amount": tender_data["value"]["amount"] * 2, "currency": "UAH"}
    await db.tenders.insert_one(open_data_1)
    await db.tenders.insert_one(open_data_2)
    assert await RiskRule().process_tender(tender_data) == RiskNotFound()


async def test_sas24_two_matching_open_tenders_no_risk(db, api):
    open_data_1 = deepcopy(open_tender_data)
    open_data_2 = deepcopy(open_tender_data)
    open_data_2["_id"] = uuid4().hex
    open_data_2["id"] = uuid4().hex
    await db.tenders.insert_one(open_data_1)
    await db.tenders.insert_one(open_data_2)
    assert await RiskRule().process_tender(tender_data) == RiskNotFound()


@pytest.mark.parametrize(
    "status,sas24_result",
    [
        ("active.tendering", RiskFound()),
        ("active.qualification", RiskFound()),
        ("active.awarded", RiskFound()),
        ("unsuccessful", RiskFound()),
        ("cancelled", RiskNotFound()),
    ],
)
async def test_sas24_open_tender_status(db, api, status, sas24_result):
    open_data = deepcopy(open_tender_data)
    open_data["status"] = status
    await db.tenders.insert_one(open_data)
    assert await RiskRule().process_tender(tender_data) == sas24_result


async def test_sas24_open_tender_started_after_reporting_has_risk(db, api):
    # Відкриті торги почалися не раніше дати звітування -> поза вікном (startDate < dateCreated) -> ризик.
    await db.tenders.insert_one(open_tender_data)  # tenderPeriod.startDate == now
    tender = deepcopy(tender_data)
    tender["dateCreated"] = (get_now() - timedelta(days=10)).isoformat()
    assert await RiskRule().process_tender(tender) == RiskFound()


@pytest.mark.parametrize(
    "days_offset,sas24_result",
    [
        (181, RiskNotFound()),  # відкриті торги в межах 365 днів -> match -> не спрацьовує
        (400, RiskFound()),  # відкриті торги поза межами 365 днів -> 0 match -> ризик
    ],
)
async def test_sas24_reporting_365_day_window(db, api, days_offset, sas24_result):
    await db.tenders.insert_one(open_tender_data)  # tenderPeriod.startDate == now
    tender = deepcopy(tender_data)
    tender["dateCreated"] = (get_now() + timedelta(days=days_offset)).isoformat()
    assert await RiskRule().process_tender(tender) == sas24_result


@pytest.mark.parametrize(
    "amount,category,sas24_result",
    [
        (40000, "services", RiskNotFound()),
        (400000, "services", RiskFound()),
        (1600000, "works", RiskFound()),
        (100000, "works", RiskNotFound()),
        (500000, "goods", RiskFound()),
        (20000, "goods", RiskNotFound()),
    ],
)
async def test_sas24_tender_value_threshold(db, amount, category, sas24_result):
    # Без відмінених відкритих торгів: вартість вище порогу -> ризик, нижче порогу -> ні.
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    assert await RiskRule().process_tender(tender) == sas24_result


# ---------------------------------------------------------------------------
# Shared "no matching open tender" cases (expectations hold for both rules).
# ---------------------------------------------------------------------------
async def test_tender_has_no_cancelled_open_tenders(db):
    assert await RiskRule().process_tender(tender_data) == RiskFound()
    assert await RiskRule2().process_tender(tender_data) == RiskNotFound()


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
    assert await RiskRule().process_tender(tender_data) == RiskFound()
    assert await RiskRule2().process_tender(tender_data) == RiskNotFound()


async def test_tender_reporting_has_another_fields(db, api):
    await db.tenders.insert_one(open_tender_data)

    tender = deepcopy(tender_data)
    tender["procuringEntityIdentifier"] = "UA-EDR-22518134"
    assert await RiskRule().process_tender(tender) == RiskFound()
    assert await RiskRule2().process_tender(tender) == RiskNotFound()

    tender["procuringEntityIdentifier"] = "UA-EDR-39604270"
    tender["dateCreated"] = (get_now() - timedelta(days=100)).isoformat()
    assert await RiskRule().process_tender(tender) == RiskFound()
    assert await RiskRule2().process_tender(tender) == RiskNotFound()

    tender["dateCreated"] = open_tender_data["tenderPeriod"]["startDate"]
    tender["subjectOfProcurement"] = "14524"
    assert await RiskRule().process_tender(tender) == RiskFound()
    assert await RiskRule2().process_tender(tender) == RiskNotFound()


# ---------------------------------------------------------------------------
# sas24-3-11-2 (legacy) specific behaviour — logic unchanged by this rework.
# ---------------------------------------------------------------------------
async def test_legacy_matching_open_tender_with_complaint_has_risk(db, api):
    await db.tenders.insert_one(open_tender_data)
    assert await RiskRule2().process_tender(tender_data) == RiskFound()


@pytest.mark.parametrize(
    "status",
    [
        "active.tendering",
        "active.qualification",
        "active.awarded",
        "cancelled",
    ],
)
async def test_legacy_open_tender_status(db, api, status):
    open_data = deepcopy(open_tender_data)
    open_data["status"] = status
    await db.tenders.insert_one(open_data)
    assert await RiskRule2().process_tender(tender_data) == RiskFound()


@pytest.mark.parametrize(
    "tender_date_created,risk_result",
    [
        ((get_now() + timedelta(days=180)).isoformat(), RiskFound()),
        ((get_now() + timedelta(days=181)).isoformat(), RiskNotFound()),
    ],
)
async def test_legacy_reporting_date_ranges(db, api, tender_date_created, risk_result):
    await db.tenders.insert_one(open_tender_data)
    tender = deepcopy(tender_data)
    tender["dateCreated"] = tender_date_created
    assert await RiskRule2().process_tender(tender) == risk_result


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
async def test_legacy_tender_value(db, api, amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    open_data = deepcopy(open_tender_data)
    open_data["value"]["amount"] = amount
    await db.tenders.insert_one(open_data)
    assert await RiskRule2().process_tender(tender) == risk_result


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


# ---------------------------------------------------------------------------
# NBU exchange: the two rules become near-opposite for value (mis)matches.
# ---------------------------------------------------------------------------
@patch(
    "prozorro.risks.utils.get_object_data",
    return_value=[{"cc": "USD", "rate": 39.5151}, {"cc": "EUR", "rate": 42.3641}],
)
@pytest.mark.parametrize(
    "amount,currency,sas24_result,legacy_result",
    [
        # value match (within ±10%) → sas24 finds a justifying cancelled tender (no risk);
        # legacy finds a matching open tender with a satisfied complaint (risk)
        (38650, "EUR", RiskNotFound(), RiskFound()),
        (37000, "USD", RiskNotFound(), RiskFound()),
        # value mismatch → sas24 has no justifying tender (risk); legacy has no match (no risk)
        (30685, "EUR", RiskFound(), RiskNotFound()),
        (44845, "EUR", RiskFound(), RiskNotFound()),
        (32900, "USD", RiskFound(), RiskNotFound()),
        (45550, "USD", RiskFound(), RiskNotFound()),
    ],
)
async def test_nbu_exchange(mock_rates, db, api, amount, currency, sas24_result, legacy_result):
    open_start = (get_now() - timedelta(days=30)).isoformat()
    open_data = deepcopy(open_tender_data)
    open_data["tenderPeriod"]["startDate"] = open_start
    open_data["value"] = {
        "amount": amount,
        "currency": currency,
    }
    await db.tenders.insert_one(open_data)

    tender = deepcopy(tender_data)
    tender["dateCreated"] = (get_now() - timedelta(days=29)).isoformat()
    assert await RiskRule().process_tender(tender) == sas24_result
    assert await RiskRule2().process_tender(tender) == legacy_result
