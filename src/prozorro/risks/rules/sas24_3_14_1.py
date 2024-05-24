from datetime import timedelta, datetime

from prozorro.risks.db import get_tenders_from_historical_data
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import calculate_end_date
from prozorro.risks.settings import SAS_24_RULES_FROM, TIMEZONE
from prozorro.risks.utils import (
    get_subject_of_procurement,
    get_exchanged_value,
    get_now,
)


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-14-1"
    owner = "sas24"
    name = "Незастосування відкритих торгів з особливостями під час закупівлі товарів або послуг"
    description = (
        "Визначення закупівель, що містять ознаки здійснення замовником протягом року закупівлі товарів або послуг "
        "за одним предметом закупівлі без проведення відкритих торгів з особливостями на суму, що дорівнює або "
        "перевищує 400 тис. грн, та/або свідчать про ймовірність допущення таких порушень."
    )
    legitimateness = (
        'Пункт 6 та 10 Особливостей № 1178, частини десятої статті 3 Закону України "Про публічні закупівлі"'
    )
    development_basis = (
        "Ознака порушення пунктів 6 та 10 Особливостей № 1178, частини десятої статті 3 Закону України "
        '"Про публічні закупівлі" з метою поділу предмета закупівлі для уникнення конкурентних процедур закупівель.'
    )
    procurement_methods = ("reporting",)
    tender_statuses = ("complete",)
    procurement_categories = ("goods", "services")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    value_for_services = 400000
    start_date = SAS_24_RULES_FROM

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, value=True):
            year = datetime.fromisoformat(tender["dateCreated"]).year
            filters = {
                "procuringEntityIdentifier": tender.get("procuringEntityIdentifier"),  # first field from compound index
                "procurementMethodType": {"$in": ("belowThreshold", "reporting")},
                "status": "complete",
                # до уваги беремо процедури, що оголошені лише в поточному році
                "dateCreated": {
                    "$gte": datetime(year, 1, 1, tzinfo=TIMEZONE).isoformat(),
                    "$lt": datetime(year + 1, 1, 1, tzinfo=TIMEZONE).isoformat(),
                },
            }
            historical_tenders = await get_tenders_from_historical_data(filters)
            year_value = 0
            for hist_tender in historical_tenders:
                if get_subject_of_procurement(hist_tender) == get_subject_of_procurement(tender):
                    if (
                        hist_tender["procurementMethodType"] in self.procurement_methods
                        and datetime.fromisoformat(hist_tender["date"]) > calculate_end_date(
                            get_now(), -timedelta(days=3)
                        )
                    ):
                        continue
                    year_value += await get_exchanged_value(hist_tender, hist_tender["dateCreated"])
            if year_value:
                for contract in tender.get("contracts", []):
                    if contract["status"] == "active":
                        contract_value = await get_exchanged_value(
                            contract, date=contract["date"]
                        )
                        # Додаємо суму з аналітичної таблиці до нашої очікуваної вартості.
                        # Якщо сума data.contracts.value виходить більша або дорівнює сумі робіт/послуг за поточний рік,
                        # то індикатор приймає значення 1.
                        value_mapping = {
                            "works": self.value_for_works,
                            "services": self.value_for_services,
                            "goods": self.value_for_services,
                        }
                        if (contract_value + year_value) >= value_mapping[tender["mainProcurementCategory"]]:
                            return RiskFound()
        return RiskNotFound()
