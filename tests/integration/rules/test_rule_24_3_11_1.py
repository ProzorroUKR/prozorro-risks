from unittest.mock import patch

import pytest
from copy import deepcopy
from datetime import timedelta

from prozorro.risks.models import RiskNotFound, RiskFound
from prozorro.risks.rules.sas24_3_11_1 import RiskRule
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
    }
)

open_tender_data = deepcopy(tender_data)
open_tender_data.update({
    "procurementMethodType": "aboveThreshold",
    "status": "cancelled",
})


async def test_tender_with_not_risky_tender_status():
    tender = deepcopy(tender_data)
    tender["status"] = "cancelled"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender = deepcopy(tender_data)
    tender["procurementMethodType"] = "priceQuotation"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


async def test_tender_has_risks(db, api):
    await db.tenders.insert_one(open_tender_data)
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_has_no_cancelled_open_tenders(db):
    risk_rule = RiskRule()
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
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_reporting_has_another_fields(db, api):
    await db.tenders.insert_one(open_tender_data)
    tender = deepcopy(tender_data)
    tender["procuringEntityIdentifier"] = "UA-EDR-22518134"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()

    tender["procuringEntityIdentifier"] = "UA-EDR-39604270"
    tender["dateCreated"] = (get_now() + timedelta(days=100)).isoformat()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()

    tender["dateCreated"] = open_tender_data["tenderPeriod"]["startDate"]
    tender["items"][0]["classification"]["id"] = "14524000-1"
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "open_items,tender_items,risk_result",
    [
        (
            [
                {"classification": {"id": "45310000-3"}},
                {"classification": {"id": "45311200-2"}},
                {"classification": {"id": "45313210-9"}},
            ],
            [
                {"classification": {"id": "45315000-8"}},
                {"classification": {"id": "45310000-3"}},
                {"classification": {"id": "45316213-1"}},
            ],
            RiskFound()
        ),
        (
            [
                {"classification": {"id": "33610000-9"}},
                {"classification": {"id": "33620000-2"}},
            ],
            [
                {"classification": {"id": "33632300-2"}},
                {"classification": {"id": "33632100-0"}},
            ],
            RiskFound()
        ),
        (
            [
                {"classification": {"id": "45234130-6"}},
                {"classification": {"id": "45234181-8"}},
            ],
            [
                {"classification": {"id": "45234240-0"}},
                {"classification": {"id": "45234250-3"}},
            ],
            RiskFound()
        ),
        (
            [
                {"classification": {"id": "45234130-6"}},
                {"classification": {"id": "45234181-8"}},
            ],
            [
                {"classification": {"id": "45230000-8"}},
                {"classification": {"id": "45234240-0"}},
                {"classification": {"id": "45234250-3"}},
            ],
            RiskNotFound()
        ),
        (
            [
                {"classification": {"id": "03111700-9"}},
                {"classification": {"id": "03111700-9"}},
            ],
            [
                {"classification": {"id": "03110000-5"}},
                {"classification": {"id": "03111000-2"}},
            ],
            RiskFound()
        ),
    ],
)
async def test_cpv_parent_codes(db, api, open_items, tender_items, risk_result):
    open_data = deepcopy(open_tender_data)
    open_data["items"] = open_items
    await db.tenders.insert_one(open_data)

    tender = deepcopy(tender_data)
    tender["items"] = tender_items
    risk_rule = RiskRule()
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
    risk_rule = RiskRule()
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
    tender["dateCreated"] = "2024-05-01T00:00:00+03:00"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result
