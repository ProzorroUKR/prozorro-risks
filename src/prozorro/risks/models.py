from enum import Enum
from pydantic import BaseModel


class RiskIndicatorEnum(str, Enum):
    risk_found = "risk_found"  # 1 індикатор спрацював, наявний ризик
    risk_not_found = "risk_not_found"  # 0 ризику немає
    use_previous_result = "use_previous_result"  # залишає останнє значення індикатора


class BaseRiskResult(BaseModel):
    type: str = "tender"
    id: str = None
    indicator: RiskIndicatorEnum


class RiskFound(BaseRiskResult):
    indicator: RiskIndicatorEnum = RiskIndicatorEnum.risk_found


class RiskNotFound(BaseRiskResult):
    indicator: RiskIndicatorEnum = RiskIndicatorEnum.risk_not_found


class RiskFromPreviousResult(BaseRiskResult):
    indicator: RiskIndicatorEnum = RiskIndicatorEnum.use_previous_result
