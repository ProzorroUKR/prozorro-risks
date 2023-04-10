from prozorro.risks.rules.sas_3_3 import RiskRule as BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "sas-3-3-1"
    name = "Закупівля робіт у одного учасника"
    procurement_categories = ("works",)
