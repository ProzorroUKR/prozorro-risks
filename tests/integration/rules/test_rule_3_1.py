from copy import deepcopy
from datetime import timedelta

import pytest
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_1 import RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")
complaints = get_fixture_json("complaints")


async def test_tender_with_satisfied_complaints_more_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_satisfied_complaints_less_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=10)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_satisfied_award_complaints_more_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    tender_data["awards"][0]["complaints"] = complaints
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_satisfied_award_complaints_less_than_decision_limit():
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=10)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender_data.pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    tender_data["awards"][0]["complaints"] = complaints
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_without_satisfied_complaints():
    tender_data.pop("complaints", None)
    tender_data["awards"][0].pop("complaints", None)
    tender_data.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


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


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFromPreviousResult()


@pytest.mark.parametrize(
    "tender_status,date_decision,risk_result",
    [
        (
            "active.pre-qualification.stand-still",
            (get_now() - timedelta(days=31)).isoformat(),
            RiskFound(),
        ),
        (
            "active.pre-qualification.stand-still",
            (get_now() - timedelta(days=10)).isoformat(),
            RiskNotFound(),
        ),
        (
            "active.pre-qualification",
            (get_now() - timedelta(days=31)).isoformat(),
            RiskFound(),
        ),
        (
            "active.pre-qualification",
            (get_now() - timedelta(days=10)).isoformat(),
            RiskNotFound(),
        ),
    ],
)
async def test_tender_on_pre_qualification_with_complaint(tender_status, date_decision, risk_result):
    complaints[0]["dateDecision"] = date_decision
    complaints[0]["status"] = "satisfied"
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "special"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": tender_status,
            "qualifications": [
                {
                    "id": "17bcbec085fd474c8057b7464c6b817c",
                    "status": "active",
                    "date": "2023-05-01T12:10:23.372754+03:00",
                    "complaints": complaints,
                }
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_on_pre_qualification_without_complaint():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "special"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.pre-qualification",
            "qualifications": [
                {
                    "id": "17bcbec085fd474c8057b7464c6b817c",
                    "status": "active",
                    "date": "2023-05-01T12:10:23.372754+03:00",
                }
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "tender_status,date_decision,risk_result",
    [
        (
            "active.tendering",
            (get_now() - timedelta(days=31)).isoformat(),
            RiskFound(),
        ),
        (
            "active.pre-qualification.stand-still",
            (get_now() - timedelta(days=10)).isoformat(),
            RiskNotFound(),
        ),
        (
            "active.pre-qualification",
            (get_now() - timedelta(days=31)).isoformat(),
            RiskFound(),
        ),
        (
            "active.awarded",
            (get_now() - timedelta(days=10)).isoformat(),
            RiskNotFound(),
        ),
    ],
)
async def test_tender_on_cancellation_with_complaint(tender_status, date_decision, risk_result):
    complaints[0]["dateDecision"] = date_decision
    complaints[0]["status"] = "satisfied"
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "special"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": tender_status,
            "cancellations": [
                {
                    "id": "17bcbec085fd474c8057b7464c6b817c",
                    "status": "active",
                    "date": "2023-05-01T12:10:23.372754+03:00",
                    "complaints": complaints,
                }
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


async def test_tender_on_cancellation_without_complaint():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "special"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.pre-qualification",
            "cancellations": [
                {
                    "id": "17bcbec085fd474c8057b7464c6b817c",
                    "status": "active",
                    "date": "2023-05-01T12:10:23.372754+03:00",
                }
            ],
        }
    )
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()
