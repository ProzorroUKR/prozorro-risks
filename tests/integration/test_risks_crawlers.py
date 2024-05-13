from unittest.mock import patch

from prozorro.risks.crawlers.contracts_crawler import process_contract
from prozorro.risks.crawlers.tenders_crawler import process_tender


@patch("prozorro.risks.crawlers.contracts_crawler.fetch_tender")
@patch("prozorro.risks.crawlers.contracts_crawler.process_risks", return_value={})
async def test_process_contracts(mock_process_risks, mock_fetch_tender, db, api):
    contract_data_1 = {
        "id": "e427359ed3614fef9a63f2e91fdafc6d",
        "tender_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe",
        "status": "terminated"
    }
    mock_fetch_tender.return_value = {
        "_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe",
        "status": "complete",
        "procurementMethodType": "aboveThresholdEU",
        "dateCreated": "2024-05-08T19:52:31.887284+03:00",
    }
    await process_contract(contract_data_1)
    result = await db.risks.find_one({"_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe"})
    assert result["terminated"] is True
    assert len(result["contracts"]) == 1

    contract_data_2 = {
        "id": "1227359ed3614fef9a63f2e91fdafc6d",
        "tender_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe",
        "status": "active"
    }
    await process_contract(contract_data_2)
    result = await db.risks.find_one({"_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe"})
    assert result["terminated"] is False
    assert len(result["contracts"]) == 2


@patch("prozorro.risks.crawlers.tenders_crawler.save_tender")
@patch("prozorro.risks.crawlers.tenders_crawler.process_risks", return_value={})
async def test_process_complete_tenders(mock_save_tender, mock_process_risks, db, api):
    tender_data = {
        "_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe",
        "status": "complete",
        "procurementMethodType": "priceQuotation",
        "dateCreated": "2024-05-08T19:52:31.887284+03:00",
        "contracts": [
            {
                "id": "e427359ed3614fef9a63f2e91fdafc6d",
                "status": "pending"
            },
            {
                "id": "1227359ed3614fef9a63f2e91fdafc6d",
                "status": "active"
            }
        ]
    }
    await process_tender(tender_data)
    result = await db.risks.find_one({"_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe"})
    assert result is None
    tender_data.update({"_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe", "procurementMethodType": "aboveThresholdEU"})
    await process_tender(tender_data)
    result = await db.risks.find_one({"_id": "94d7d8f4aaf647c8bbe99ce71f8ebefe"})
    assert result["terminated"] is False
    assert len(result["contracts"]) == 2
