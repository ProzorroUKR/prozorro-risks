from unittest.mock import patch
from uuid import uuid4

import pytest
from copy import deepcopy
from datetime import timedelta, datetime

from prozorro.risks.models import RiskNotFound, RiskFound
from prozorro.risks.rules.sas24_3_14_1 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
tender_data["mainProcurementCategory"] = "services"
tender_data["value"]["amount"] = 400000
tender_data.update(
    {
        "procurementMethodType": "reporting",
        "status": "complete",
        "dateCreated": (get_now() - timedelta(days=5)).isoformat(),
    }
)
contract = get_fixture_json("contract")
contract["value"]["amount"] = 100000
tender_data["contracts"] = [contract]

history_tender_data = deepcopy(tender_data)
history_tender_data.update({
    "date": (get_now() - timedelta(days=3)).isoformat(),
})
history_tender_data["value"]["amount"] = 300000


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
    await db.tenders.insert_one(history_tender_data)
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_has_no_completed_historical_tenders(db):
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "not_matched_data",
    [
        ({"status": "cancelled"}),
        ({"procurementMethodType": "priceQuotation"}),
        ({"date": (get_now() - timedelta(days=2)).isoformat()}),
        ({"dateCreated": datetime(year=2023, month=12, day=15).isoformat()}),
        ({"procuringEntityIdentifier": "UA-EDR-22518134"}),
    ],
)
async def test_tender_has_open_tenders_with_another_fields(db, api, not_matched_data):
    history_data = deepcopy(history_tender_data)
    history_data.update(not_matched_data)
    await db.tenders.insert_one(history_data)
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
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
    hist_data = deepcopy(history_tender_data)
    hist_data["items"] = open_items
    await db.tenders.insert_one(hist_data)

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
        (1600000, "works", RiskNotFound()),
        (500000, "goods", RiskFound()),
        (20000, "goods", RiskNotFound()),
    ],
)
async def test_tender_value(db, api, amount, category, risk_result):
    tender = deepcopy(tender_data)
    tender["mainProcurementCategory"] = category
    tender["value"]["amount"] = amount
    hist_data = deepcopy(history_tender_data)
    hist_data["value"]["amount"] = amount
    await db.tenders.insert_one(hist_data)
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
        (7082, "EUR", RiskFound()),
        (7081, "EUR", RiskNotFound()),
        (7593, "USD", RiskFound()),
        (7591, "USD", RiskNotFound()),
    ],
)
async def test_nbu_exchange(mock_rates, db, api, amount, currency, risk_result):
    hist_data = deepcopy(history_tender_data)
    hist_data["dateCreated"] = "2024-05-01T00:00:00+03:00"
    hist_data["value"] = {
        "amount": amount,
        "currency": currency,
    }
    await db.tenders.insert_one(hist_data)

    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == risk_result


async def test_historical_tenders_has_less_year_amount(db, api):
    history_tender_1 = deepcopy(history_tender_data)
    history_tender_1["value"]["amount"] = 100000
    await db.tenders.insert_one(history_tender_1)

    history_tender_2 = deepcopy(history_tender_1)
    history_tender_2["date"] = (get_now() - timedelta(days=2)).isoformat()  # should be skipped
    history_tender_2["_id"] = uuid4().hex
    await db.tenders.insert_one(history_tender_2)

    history_tender_3 = deepcopy(history_tender_1)
    history_tender_3["procurementMethodType"] = "belowThreshold"
    history_tender_3["_id"] = uuid4().hex
    await db.tenders.insert_one(history_tender_3)

    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()  # 200000 from historical tenders + 100000 contract < 400000
