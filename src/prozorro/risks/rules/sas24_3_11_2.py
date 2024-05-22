from datetime import timedelta

from prozorro.risks.db import get_tenders_from_historical_data
from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import calculate_end_date, get_complaints, flatten
from prozorro.risks.settings import SAS_24_RULES_FROM
from prozorro.risks.utils import get_subject_of_procurement, get_exchanged_value


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-11-2"
    owner = "sas24"
    name = (
        "Укладання замовником договору про закупівлю без використання електронної системи закупівель під час "
        "оскарження процедури закупівлі за аналогічним предметом закупівлі"
    )
    description = (
        "Визначення закупівель, що містять ознаки неправомірного оприлюднення звіту про укладений договір без "
        "застосування електронної системи закупівель за наявності відкритих торгів за аналогічним предметом закупівлі "
        "зі скаргою до Органу оскарження, та/або свідчать про ймовірність допущення таких порушень"
    )
    legitimateness = (
        'Пункт 5 та пункт 13 Особливостей № 1178, частина 10 статті 3 Закону України "Про публічні закупівлі"'
    )
    development_basis = (
        'Ознака порушення пункту 5 та пункту 13 Особливостей № 1178, частина 10 статті 3 Закону України '
        '"Про публічні закупівлі" в частині безпідставного придбання замовниками робіт до/без проведення процедури '
        'закупівлі відкриті торги/ використання електронного каталогу (у разі закупівлі товару), '
        'та укладення договорів про закупівлю, які передбачають оплату замовником товарів, робіт і послуг до/без '
        'проведення процедури закупівлі відкриті торги/використання електронного каталогу (у разі закупівлі товару)'
    )
    procurement_methods = ("reporting",)
    tender_statuses = ("complete",)
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
        "defense",
    )
    value_for_services = 400000
    value_for_works = 1500000
    start_date = SAS_24_RULES_FROM

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True):
            # В рамках одного коду ЄДРПОУ замовника data.procuringEntity.identifier.id порівнюємо
            # data.procurement.MethodType = reporting зі статусом data.status = complete,
            # з data.procurement.MethodType = aboveThreshold, = aboveThresholdUA, = aboveThresholdEU
            # зі статусами data.status="active.tendering", "cancelled", "unsuccessful", "active.qualification",
            # "active.awarded".
            filters = {
                "procuringEntityIdentifier": tender.get("procuringEntityIdentifier"),  # first field from compound index
                # data.title звітування співпадає з data.title з будь-якої закупівлі відкритих торгі
                "title": tender.get("title"),
                "procurementMethodType": {"$in": ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")},
                "status": {"$in": (
                    "active.tendering", "cancelled", "unsuccessful", "active.qualification", "active.awarded"
                )},
                # data.tender.dateCreated звітування молодша та є в межах 180 днів від data.tenderPeriod.startDate
                "tenderPeriod.startDate": {
                    "$gte": tender["dateCreated"],
                    "$lt": calculate_end_date(tender["dateCreated"], timedelta(days=180)).isoformat(),
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
                        # В процедурі відкритих торгів присутні блоки data.complaints, data.awards.complaints,
                        # data.qualification:complaints або data.cancellations:complaints. що
                        # мають complaints.type='complaint' та complaints.status = 'satisfied'.
                        complaints = get_complaints(open_tender, statuses=["satisfied"])
                        award_complaints = flatten(
                            [
                                get_complaints(award, statuses=["satisfied"])
                                for award in open_tender.get("awards", [])
                            ]
                        )
                        cancellation_complaints = flatten(
                            [
                                get_complaints(cancellation, statuses=["satisfied"])
                                for cancellation in open_tender.get("cancellations", [])
                            ]
                        )
                        qualifications_complaints = flatten(
                            [
                                get_complaints(qualification, statuses=["satisfied"])
                                for qualification in open_tender.get("qualifications", [])
                            ]
                        )
                        if any([complaints, award_complaints, cancellation_complaints, qualifications_complaints]):
                            return RiskFound()
        return RiskNotFound()
