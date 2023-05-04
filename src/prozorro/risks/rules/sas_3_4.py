from datetime import datetime

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseContractRiskRule
from prozorro.risks.rules.utils import count_days_between_two_dates
from prozorro.risks.settings import CRAWLER_START_DATE
from prozorro.risks.utils import fetch_tender

SIGNING_DAYS_LIMIT = 90


class RiskRule(BaseContractRiskRule):
    identifier = "sas-3-4"
    name = "Зміна істотних умов договору (ціни за одиницю товару)"
    description = "Індикатор свідчить про незаконну зміну ціни договору частіше ніж один раз у 90 днів"
    legitimateness = (
        "Зміна суми договру частіше ніж один раз на 90 днів є порушенням пп. 2, п. 5 статті 41 Закону "
        "про публічні закупівлі"
    )
    development_basis = "Автоматичний контроль терміном внесення змін до договору відсутній в системі."
    contract_statuses = ("active",)
    stop_assessment_status = "terminated"
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )

    async def process_contract(self, contract):
        if contract["status"] in self.contract_statuses:
            # В контракті по полю data.tender_id знаходимо відповідний тендер
            tender = await fetch_tender(contract["tender_id"])
            if datetime.fromisoformat(tender["dateCreated"]) < CRAWLER_START_DATE:
                raise SkipException()
            if tender.get("procuringEntity", {}).get("kind") in self.procuring_entity_kinds:
                active_changes = [
                    change
                    for change in contract.get("changes", [])
                    if change["status"] == "active" and "itemPriceVariation" in change["rationaleTypes"]
                ]
                # Якщо в договорі немає змін у яких data.changes.status='active' та
                # в масив причин data.changes.rationaleTypes містить елемент itemPriceVariation,
                # індикатор приймає значення 0, розрахунок завершується
                if not active_changes:
                    return RiskIndicatorEnum.risk_not_found

                #  Вибираємо всі дати підписання з таких елементів, впорядковуємо дати за зростанням
                dates = sorted([change.get("dateSigned") for change in active_changes])

                # Попарно перевіряємо відстань у днях між елементами списку
                for idx, date in enumerate(dates[:-1]):
                    # Якщо хоч одна відстань між елементам менша за 90 днів, індикатор приймає значення 1,
                    # розрахунок завершується
                    if count_days_between_two_dates(dates[idx + 1], date) < SIGNING_DAYS_LIMIT:
                        return RiskIndicatorEnum.risk_found
        elif contract["status"] == self.stop_assessment_status:
            return RiskIndicatorEnum.use_previous_result
        return RiskIndicatorEnum.risk_not_found
