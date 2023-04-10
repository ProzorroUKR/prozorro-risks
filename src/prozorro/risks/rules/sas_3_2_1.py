from prozorro.risks.rules.sas_3_2 import RiskRule as BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "sas-3-2-1"
    name = "Замовник відхилив тендерні пропозиції всіх учасників під час закупівлі робіт, крім переможця"
    procurement_categories = ("works",)
