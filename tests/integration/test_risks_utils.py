import pytest
from copy import deepcopy

from prozorro.risks.utils import get_subject_of_procurement
from tests.integration.conftest import get_fixture_json

tender_data = get_fixture_json("base_tender")


@pytest.mark.parametrize(
    "tender_items_1,tender_items_2,result",
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
            True
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
            True
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
            True
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
            False
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
            True
        ),
    ],
)
async def test_cpv_parent_codes(db, api, tender_items_1, tender_items_2, result):
    tender_1 = deepcopy(tender_data)
    tender_1["items"] = tender_items_1

    tender_2 = deepcopy(tender_data)
    tender_2["items"] = tender_items_2
    condition = get_subject_of_procurement(tender_1) == get_subject_of_procurement(tender_2)
    assert condition is result
