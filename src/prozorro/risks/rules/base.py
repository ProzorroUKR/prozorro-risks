from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from prozorro.risks.rules.utils import calculate_end_date
from prozorro.risks.utils import get_now


class BaseRiskRule(ABC):
    identifier: str
    name: str
    owner: str = "sas"
    description: str = None
    legitimateness: str = None
    development_basis: str = None
    procurement_methods: tuple
    tender_statuses: tuple
    procurement_categories: tuple
    procuring_entity_kinds: tuple
    contract_statuses: tuple
    start_date: str = None
    end_date: str = None
    stop_assessment_status: str = "complete"
    value_for_services: int = 0
    value_for_works: int = 0
    max_tender_age_days: int = None

    def tender_matches_requirements(self, tender, status=True, category=True, value=False):
        status_matches = tender["status"] in self.tender_statuses if status else True
        category_matches = tender.get("mainProcurementCategory") in self.procurement_categories if category else True
        value_matches = (
            (
                tender.get("mainProcurementCategory") in ("goods", "services")
                and float(tender.get("value", {}).get("amount", 0)) >= self.value_for_services
            ) or (
                tender.get("mainProcurementCategory") == "works"
                and float(tender.get("value", {}).get("amount", 0)) >= self.value_for_works
            )
        ) if value else True

        age_matches = True
        if self.max_tender_age_days is not None and tender.get("dateCreated"):
            cutoff = calculate_end_date(
                get_now(),
                -timedelta(days=self.max_tender_age_days),
                normalized=False,
            )
            age_matches = datetime.fromisoformat(tender["dateCreated"]) >= cutoff

        return (
            tender["procurementMethodType"] in self.procurement_methods
            and status_matches
            and tender.get("procuringEntity", {}).get("kind", "other") in self.procuring_entity_kinds
            and category_matches
            and value_matches
            and age_matches
        )


class BaseTenderRiskRule(BaseRiskRule):
    @classmethod
    @abstractmethod
    def process_tender(cls, tender, parent_object=None):
        ...


class BaseContractRiskRule(BaseRiskRule):
    @classmethod
    @abstractmethod
    def process_contract(cls, contract, parent_object=None):
        ...
