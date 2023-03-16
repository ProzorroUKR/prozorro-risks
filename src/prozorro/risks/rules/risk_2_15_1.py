from prozorro.risks.rules.risk_2_15 import RiskRule as BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "2-15-1"
    name = "Закупівля робіт у одного учасника"
    procurement_categories = ("works",)
