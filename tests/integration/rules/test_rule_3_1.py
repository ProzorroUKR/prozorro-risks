from copy import deepcopy
from datetime import timedelta

import pytest
from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_1 import RiskRule
from prozorro.risks.rules.sas24_3_1 import RiskRule as Sas24RiskRule
from prozorro.risks.utils import get_now
from tests.integration.conftest import get_fixture_json

tender_data = deepcopy(get_fixture_json("base_tender"))
complaints = get_fixture_json("complaints")
tender_data["mainProcurementCategory"] = "services"
tender_data["value"]["amount"] = 500000
tender_data["dateModified"] = (get_now() - timedelta(days=31)).isoformat()


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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_tender_status():
    tender_data.update(
        {
            "status": "cancelled",
        }
    )
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_type():
    tender_data.update(
        {
            "procurementMethodType": "reporting",
        }
    )
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender_data)
        assert result == RiskNotFound()


async def test_tender_with_not_risky_procurement_entity_kind():
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "other"
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()


@pytest.mark.parametrize(
    "risk_rule_class,risk_result",
    [
        (RiskRule, RiskFromPreviousResult()),
        (Sas24RiskRule, RiskFound()),
    ],
)
async def test_tender_with_complete_status(risk_rule_class, risk_result):
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender = deepcopy(tender_data)
    tender["procuringEntity"]["kind"] = "defense"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
        }
    )
    tender["status"] = "complete"
    risk_rule = risk_rule_class()
    result = await risk_rule.process_tender(tender)
    assert result == risk_result


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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == risk_result


@pytest.mark.parametrize(
    "amount,category,risk_rule_class,risk_result",
    [
        (400000, "services", RiskRule, RiskFound()),
        (400000, "services", Sas24RiskRule, RiskFound()),
        (1600000, "works", RiskRule, RiskFound()),
        (1600000, "works", Sas24RiskRule, RiskFound()),
        (20000, "goods", RiskRule, RiskFound()),
        (20000, "goods", Sas24RiskRule, RiskNotFound()),
        (600000, "works", RiskRule, RiskFound()),
        (600000, "works", Sas24RiskRule, RiskNotFound()),
    ],
)
async def test_tender_value(amount, category, risk_rule_class, risk_result):
    tender = deepcopy(tender_data)
    complaints[0]["dateDecision"] = (get_now() - timedelta(days=31)).isoformat()
    complaints[0]["status"] = "satisfied"
    tender.update(
        {
            "procurementMethodType": "aboveThresholdEU",
            "status": "active.tendering",
            "complaints": complaints,
            "mainProcurementCategory": category,
        }
    )
    tender["value"]["amount"] = amount
    risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
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
    for risk_rule_class in (RiskRule, Sas24RiskRule):
        risk_rule = risk_rule_class()
        result = await risk_rule.process_tender(tender)
        assert result == RiskNotFound()
