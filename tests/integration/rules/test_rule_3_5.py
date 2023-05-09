import pytest
from copy import deepcopy

from prozorro.risks.models import RiskFound, RiskNotFound, RiskFromPreviousResult
from prozorro.risks.rules.sas_3_5 import RiskRule
from tests.integration.conftest import get_fixture_json


tender_data = get_fixture_json("base_tender")
tender_data["procuringEntity"]["kind"] = "general"
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

disqualified_award = get_fixture_json("disqualified_award")


async def test_tender_without_disqualified_award():
    tender_data["awards"] = [tender_data["awards"][0]]
    tender_data["awards"][0]["lotID"] = tender_data["lots"][0]["id"]
    tender_data["awards"][0]["status"] = "active"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_1_disqualified_award_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender_data["awards"] = [disqualified_award]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_2_disqualified_award_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender_data["awards"] = [disqualified_award, disqualified_award]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_more_than_2_disqualified_award_without_lots():
    tender = deepcopy(tender_data)
    tender.pop("lots", None)
    tender_data["awards"] = [disqualified_award, disqualified_award, disqualified_award]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_1_disqualified_award_with_related_lots():
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    tender_data["awards"] = [disqualified_award]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskNotFound()


async def test_tender_with_2_disqualified_award_with_related_lots():
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    tender_data["awards"] = [disqualified_award, disqualified_award]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFound()


async def test_tender_with_1_disqualified_award_with_one_related_lots_and_1_for_another():
    tender = deepcopy(tender_data)
    tender["lots"].append(
        {
            "title": "Бетон та розчин будівельний",
            "status": "active",
            "id": "c2bb6ff3e8e547bee11d8bff23e8a290",
        }
    )
    disqualified_award["lotID"] = tender_data["lots"][0]["id"]
    disqualified_award_2 = deepcopy(disqualified_award)
    disqualified_award_2["lotID"] = "c2bb6ff3e8e547bee11d8bff23e8a290"
    tender["awards"] = [disqualified_award, disqualified_award_2]
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender)
    assert result == RiskNotFound()


@pytest.mark.parametrize(
    "lot_status,risk_result",
    [
        ("active", RiskFound()),
        ("cancelled", RiskNotFound()),
        ("unsuccessful", RiskNotFound()),
    ],
)
async def test_tender_with_more_than_2_disqualified_award_with_related_lots(lot_status, risk_result):
    tender = deepcopy(tender_data)
    tender["lots"][0]["status"] = lot_status
    disqualified_award["lotID"] = tender["lots"][0]["id"]
    tender_data["awards"] = [disqualified_award] * 3
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


async def test_tender_with_complete_status():
    tender_data["status"] = "complete"
    risk_rule = RiskRule()
    result = await risk_rule.process_tender(tender_data)
    assert result == RiskFromPreviousResult()
