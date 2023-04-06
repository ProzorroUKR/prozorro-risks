from enum import Enum


class RiskIndicatorEnum(str, Enum):
    risk_found = "risk_found"  # 1 індикатор спрацював, наявний ризик
    risk_not_found = "risk_not_found"  # 0 ризику немає
