from copy import deepcopy

from prozorro.risks.db import update_tender_risks
from tests.integration.conftest import get_fixture_json

tender = get_fixture_json("risks")
tender_with_3_1_risk_found = deepcopy(tender)
tender_with_3_1_risk_found["risks"]["worked"] = [
    {
        "id": "3-1",
        "indicator": "risk_found",
        "date": "2023-03-13T14:37:12.491341+02:00",
    }
]


async def test_update_tender_risks_with_already_existed_one(db):
    tender_obj = await db.risks.insert_one(tender_with_3_1_risk_found)
    risks = {
        "worked": [
            {
                "id": "3-1",
                "indicator": "risk_found",
                "date": "2023-03-21T14:37:12.491341+02:00",
            }
        ],
        "other": [
            {
                "id": "3-2",
                "indicator": "risk_not_found",
                "date": "2023-03-21T14:37:12.491341+02:00",
            }
        ],
    }
    await update_tender_risks(tender_obj.inserted_id, risks, {"dateAssessed": "2023-03-21T14:37:12.491341+02:00"})
    result = await db.risks.find_one(tender_obj.inserted_id)
    assert len(result["risks"]["worked"]) == 1
    assert result["risks"]["worked"][0]["date"] == "2023-03-21T14:37:12.491341+02:00"
    assert len(result["risks"]["other"]) == 2  # previously count 3-2-1 and newly count 3-2
    assert result["risks"]["other"][0]["date"] == "2023-03-21T14:37:12.491341+02:00"


async def test_update_tender_risks_with_non_existed_one(db):
    risks = {
        "worked": [
            {
                "id": "3-1",
                "indicator": "risk_found",
                "date": "2023-03-21T14:37:12.491341+02:00",
            }
        ],
        "other": [
            {
                "id": "3-2",
                "indicator": "risk_not_found",
                "date": "2023-03-21T14:37:12.491341+02:00",
            }
        ],
    }
    await update_tender_risks(
        "bab6d5f695cc4b51a7a5bdaff8181550", risks, {"dateAssessed": "2023-03-21T14:37:12.491341+02:00"}
    )
    result = await db.risks.find_one({"_id": "bab6d5f695cc4b51a7a5bdaff8181550"})
    assert len(result["risks"]["worked"]) == 1
    assert len(result["risks"]["other"]) == 1
    assert "dateAssessed" in result
