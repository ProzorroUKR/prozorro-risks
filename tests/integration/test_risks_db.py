from copy import deepcopy

from prozorro.risks.db import update_tender_risks
from tests.integration.conftest import get_fixture_json

tender = get_fixture_json("risks")
tender_with_3_1_risk_found = deepcopy(tender)
tender_with_3_1_risk_found["_id"] = "f59a674045ac4c349a220c8fbaf184b9"
tender_with_3_1_risk_found["risks"] = {
    "3-1": {
        "indicator": "risk_found",
        "date": "2023-03-13T14:37:12.491341+02:00",
        "history": [{"date": "2023-03-13T14:37:12.491341+02:00", "indicator": "risk_found"}],
    },
    "3-2-1": {
        "indicator": "risk_not_found",
        "date": "2023-03-13T14:37:12.491341+02:00",
        "history": [{"date": "2023-03-13T14:37:12.491341+02:00", "indicator": "risk_not_found"}],
    },
}
tender_with_3_1_risk_found["worked_risks"] = ["3-1"]


async def test_update_tender_risks_with_already_existed_one(db):
    tender_obj = await db.risks.insert_one(tender_with_3_1_risk_found)
    risks = {
        "3-1": {
            "indicator": "risk_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
        "3-2": {
            "indicator": "risk_not_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
    }
    await update_tender_risks(tender_obj.inserted_id, risks, {"dateAssessed": "2023-03-21T14:37:12.491341+02:00"})
    result = await db.risks.find_one(tender_obj.inserted_id)
    assert result["worked_risks"] == ["3-1"]
    assert len(result["risks"].keys()) == 3
    assert result["risks"]["3-1"]["date"] == "2023-03-21T14:37:12.491341+02:00"
    assert len(result["risks"]["3-1"]["history"]) == 2
    assert len(result["risks"]["3-2-1"]["history"]) == 1
    assert len(result["risks"]["3-2"]["history"]) == 1


async def test_update_tender_risks_with_non_existed_one(db):
    risks = {
        "3-1": {
            "indicator": "risk_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
        "3-2": {
            "indicator": "risk_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
    }
    await update_tender_risks(
        "bab6d5f695cc4b51a7a5bdaff8181550", risks, {"dateAssessed": "2023-03-21T14:37:12.491341+02:00"}
    )
    result = await db.risks.find_one({"_id": "bab6d5f695cc4b51a7a5bdaff8181550"})
    assert len(result["worked_risks"]) == 2
    assert len(result["risks"].keys()) == 2
    assert result["risks"]["3-1"]["indicator"] == "risk_found"
    assert len(result["risks"]["3-1"]["history"]) == 1
    assert len(result["risks"]["3-2"]["history"]) == 1
    assert "dateAssessed" in result


async def test_update_tender_with_previously_worked_risks(db):
    risks = {
        "3-1": {
            "indicator": "risk_not_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
        "3-2": {
            "indicator": "risk_found",
            "date": "2023-03-21T14:37:12.491341+02:00",
        },
    }
    result = await db.risks.find_one("f59a674045ac4c349a220c8fbaf184b9")
    assert result["worked_risks"] == ["3-1"]
    await update_tender_risks(result["_id"], risks, {"dateAssessed": "2023-03-21T14:37:12.491341+02:00"})
    result = await db.risks.find_one(result["_id"])
    assert result["worked_risks"] == ["3-2"]
    assert len(result["risks"].keys()) == 3
