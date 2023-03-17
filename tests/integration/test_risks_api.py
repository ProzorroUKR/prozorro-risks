from copy import deepcopy
from bson.objectid import ObjectId
from tests.integration.conftest import get_fixture_json

tender = get_fixture_json("risks")
tender_with_1_13_risk_found = deepcopy(tender)
tender_with_1_13_risk_found["risks"]["worked"] = [
    {
        "id": "1-13",
        "indicator": "risk_found",
        "date": "2023-03-13T14:37:12.491341+02:00",
    }
]

tender_with_2_4_risk_found = deepcopy(tender)
tender_with_2_4_risk_found["risks"]["worked"] = [
    {"id": "2-4", "indicator": "risk_found", "date": "2023-03-13T14:37:12.491341+02:00"}
]

tender_with_no_risks_found = deepcopy(tender)
tender_with_no_risks_found["risks"]["worked"] = []


async def test_list_tenders_count(api, db):
    await db.risks.insert_many([tender_with_no_risks_found, tender])
    response = await api.get("/api/risks")
    assert response.status == 200
    resp_json = await response.json()
    assert "items" in resp_json
    assert "count" in resp_json
    assert resp_json["count"] == 2


async def test_list_tenders_skip_and_limit(api, db):
    await db.risks.insert_many(
        [tender_with_no_risks_found, tender_with_1_13_risk_found, tender]
    )
    response = await api.get("/api/risks?limit=1")
    assert response.status == 200
    resp_json = await response.json()
    assert len(resp_json["items"]) == 1
    assert resp_json["count"] == 3

    response = await api.get("/api/risks?skip=2")
    assert response.status == 200
    resp_json = await response.json()
    assert len(resp_json["items"]) == 1
    assert resp_json["count"] == 3


async def test_list_tenders_sort_by_date_modified(api, db):
    tender["dateModified"] = "2018-03-14T21:37:16.832566+02:00"
    tender_with_no_risks_found["dateModified"] = "2019-02-14T21:37:16.832566+02:00"
    tender_with_1_13_risk_found["dateModified"] = "2019-03-14T21:37:16.832566+02:00"
    await db.risks.insert_many(
        [tender, tender_with_no_risks_found, tender_with_1_13_risk_found]
    )
    response = await api.get("/api/risks?order=asc")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["items"][0]["dateModified"] == tender["dateModified"]
    assert (
        resp_json["items"][-1]["dateModified"]
        == tender_with_1_13_risk_found["dateModified"]
    )

    response = await api.get("/api/risks?order=desc")
    assert response.status == 200
    resp_json = await response.json()
    assert (
        resp_json["items"][0]["dateModified"]
        == tender_with_1_13_risk_found["dateModified"]
    )
    assert resp_json["items"][-1]["dateModified"] == tender["dateModified"]


async def test_list_tenders_sort_by_value_amount(api, db):
    tender["value"]["amount"] = 10000
    tender_with_no_risks_found["value"]["amount"] = 20000
    tender_with_1_13_risk_found["value"]["amount"] = 400000
    await db.risks.insert_many(
        [tender, tender_with_no_risks_found, tender_with_1_13_risk_found]
    )
    response = await api.get("/api/risks?sort=value.amount&order=asc")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["items"][0]["value"]["amount"] == tender["value"]["amount"]
    assert (
        resp_json["items"][-1]["value"]["amount"]
        == tender_with_1_13_risk_found["value"]["amount"]
    )

    response = await api.get("/api/risks?sort=value.amount")
    assert response.status == 200
    resp_json = await response.json()
    assert (
        resp_json["items"][0]["value"]["amount"]
        == tender_with_1_13_risk_found["value"]["amount"]
    )
    assert resp_json["items"][-1]["value"]["amount"] == tender["value"]["amount"]


async def test_list_tenders_filter_by_risks_worked(api, db):
    await db.risks.insert_many(
        [
            tender_with_no_risks_found,
            tender_with_1_13_risk_found,
            tender_with_2_4_risk_found,
        ]
    )
    response = await api.get("/api/risks?risks=1-13")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 1
    assert resp_json["items"][0]["risks"]["worked"][0]["id"] == "1-13"

    response = await api.get("/api/risks?risks=2-4")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 1
    assert resp_json["items"][0]["risks"]["worked"][0]["id"] == "2-4"

    response = await api.get("/api/risks?risks=1-13;2-4")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 2
    assert resp_json["items"][0]["risks"]["worked"][0]["id"] in ("1-13", "2-4")
    assert resp_json["items"][0]["risks"]["worked"][-1]["id"] in ("1-13", "2-4")

    response = await api.get("/api/risks?risks=2-4-1")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 0


async def test_list_tenders_filter_by_region(api, db):
    tender_with_no_risks_found["procuringEntityRegion"] = "харківська область"
    tender_with_no_risks_found["procuringEntity"]["address"][
        "region"
    ] = "Харківська область"
    await db.risks.insert_many(
        [
            tender_with_no_risks_found,
            tender_with_1_13_risk_found,
            tender_with_2_4_risk_found,
        ]
    )
    response = await api.get("/api/risks?region=Харківська область")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 1
    assert (
        resp_json["items"][0]["procuringEntity"]["address"]["region"]
        == "Харківська область"
    )

    response = await api.get("/api/risks?region=Полтавська область")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["count"] == 2
    assert (
        resp_json["items"][0]["procuringEntity"]["address"]["region"]
        in "Полтавська область"
    )
    assert (
        resp_json["items"][0]["procuringEntity"]["address"]["region"]
        in "Полтавська область"
    )


async def test_get_risks(api, db):
    tender_with_1_13_risk_found["_id"] = "bab6d5f695cc4b51a7a5bdaff8181550"
    tender_obj = await db.risks.insert_one(tender_with_1_13_risk_found)
    response = await api.get(f"/api/risks/{tender_obj.inserted_id}")
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json["risks"]["worked"][0]["id"] == "1-13"

    response = await api.get(f"/api/risks/{str(ObjectId())}")
    assert response.status == 404
