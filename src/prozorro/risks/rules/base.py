from abc import ABC, abstractmethod


class BaseRiskRule(ABC):
    identifier: str
    name: str
    description: str
    legitimateness: str
    development_basis: str
    procurement_methods: tuple
    tender_statuses: tuple
    procurement_categories: tuple
    procuring_entity_kinds: tuple
    contract_statuses: tuple

    @classmethod
    @abstractmethod
    def process_tender(cls, tender):
        ...
