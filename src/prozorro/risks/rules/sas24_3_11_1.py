from datetime import timedelta

from prozorro.risks.db import get_tenders_from_historical_data
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import calculate_end_date
from prozorro.risks.settings import SAS_24_RULES_FROM
from prozorro.risks.utils import get_subject_of_procurement, get_exchanged_value


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-11-1"
    owner = "sas24"
    name = (
        "Укладання замовником договору про закупівлю на закупівлі товарів або послуг, виконання робіт без "
        "використання електронної системи закупівель (відміна відкритих торгів)"
    )
    description = (
        "Визначення закупівель, що містять ознаки порушень законодавства щодо неправомірного оприлюднення замовником "
        "звіту про укладання договору про закупівлю за відсутності відміни відкритих торгів через неподання жодної "
        "тендерної пропозиції для участі у відкритих торгах за аналогічним предметом закупівлі, "
        "та/або свідчать про ймовірність допущення таких порушень"
    )
    legitimateness = (
        'Підпункт 5 та підпункт 6 пункту 13 Особливостей № 1178, частина 10 статті 3 Закону '
        'України "Про публічні закупівлі"'
    )
    development_basis = (
        'Ознака порушення підпункту 5 та підпункту 6 пункту 13 Особливостей № 1178, частина 10 статті 3 Закону '
        'України "Про публічні закупівлі" в частині безпідставного придбання замовником робіт до/без проведення '
        'процедури закупівлі відкриті торги, та укладення договорів про закупівлю, які передбачають оплату замовником '
        'товарів, робіт і послуг до/без проведення процедури закупівлі відкриті '
        'торги/ використання електронного каталогу (у разі закупівлі товару)'
    )
    procurement_methods = ("reporting",)
    tender_statuses = ("complete",)
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    value_for_services = 400000
    value_for_works = 1500000
    start_date = SAS_24_RULES_FROM

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True):
            # В рамках одного коду ЄДРПОУ замовника data.procuringEntity.identifier.id порівнюємо
            # data.procurement.MethodType = reporting зі статусом data.status = complete,
            # з data.procurement.MethodType = aboveThreshold, = aboveThresholdUA, = aboveThresholdEU
            # зі статусами data.status=cancelled.
            filters = {
                "procuringEntityIdentifier": tender.get("procuringEntityIdentifier"),  # first field from compound index
                # data.title звітування співпадає з data.title з будь-якої закупівлі відкритих торгі
                "title": tender.get("title"),
                "procurementMethodType": {"$in": ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")},
                "status": "cancelled",
                # data.tender.dateCreated звітування молодша та є в межах 365 днів від data.tenderPeriod.startDate
                "tenderPeriod.startDate": {
                    "$gte": tender["dateCreated"],
                    "$lt": calculate_end_date(tender["dateCreated"], timedelta(days=365)).isoformat(),
                },
            }
            open_tenders = await get_tenders_from_historical_data(filters)
            for open_tender in open_tenders:
                # якщо відкриті торги і звіт мають один tv_subjectOfProcurement
                if get_subject_of_procurement(open_tender) == get_subject_of_procurement(tender):
                    tender_value = await get_exchanged_value(tender, date=tender["dateCreated"])
                    open_tender_value = await get_exchanged_value(open_tender, open_tender["tenderPeriod"]["startDate"])
                    # data.value.amount в гривнях на дату звітування знаходиться в межах +-10% від data.value.amount
                    # в гривнях відповідних відкритих торгів
                    if abs(tender_value - open_tender_value) <= open_tender_value * 0.1:
                        return RiskFound()
        return RiskNotFound()
