from prozorro.risks.rules.risk_2_19 import RiskRule as BaseRiskRule


class RiskRule(BaseRiskRule):
    identifier = "2-19-1"
    name = "Відхилення 2-х тендерних пропозицій/пропозицій"

    def process_tender(self, tender):
        return self.process_tender_with_cancelled_proposition(tender, lots_limit=2)
