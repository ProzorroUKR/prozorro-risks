from abc import ABC, abstractmethod


class BaseRiskRule(ABC):
    identifier: str
    name: str
    description: str = None
    legitimateness: str = None
    development_basis: str = None
    procurement_methods: tuple
    tender_statuses: tuple
    procurement_categories: tuple
    procuring_entity_kinds: tuple
    contract_statuses: tuple

    def tender_matches_requirements(self, tender, status=True, category=True):
        status_matches = tender["status"] in self.tender_statuses if status else True
        category_matches = tender.get("mainProcurementCategory") in self.procurement_categories if category else True
        return (
            tender["procurementMethodType"] in self.procurement_methods
            and status_matches
            and tender["procuringEntity"]["kind"] in self.procuring_entity_kinds
            and category_matches
        )


class BaseTenderRiskRule(BaseRiskRule):
    @classmethod
    @abstractmethod
    def process_tender(cls, tender):
        ...


class BaseContractRiskRule(BaseRiskRule):
    @classmethod
    @abstractmethod
    def process_contract(cls, contract):
        ...
