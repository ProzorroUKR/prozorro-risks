from abc import ABC, abstractmethod


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
    start_date: str = "2023-01-01"
    end_date: str = None
    stop_assessment_status: str = "complete"
    value_for_services: int = 0
    value_for_works: int = 0

    def tender_matches_requirements(self, tender, status=True, category=True, value=False):
        status_matches = tender["status"] in self.tender_statuses if status else True
        category_matches = tender.get("mainProcurementCategory") in self.procurement_categories if category else True
        value_matches = (
            (
                tender.get("mainProcurementCategory") in ("goods", "services")
                and tender.get("value", {}).get("amount", 0) >= self.value_for_services
            ) or (
                tender.get("mainProcurementCategory") == "works"
                and tender.get("value", {}).get("amount", 0) >= self.value_for_works
            )
        ) if value else True
        return (
            tender["procurementMethodType"] in self.procurement_methods
            and status_matches
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
            and category_matches
            and value_matches
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
