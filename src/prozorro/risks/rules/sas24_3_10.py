from datetime import datetime, timedelta

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import is_winner_awarded, calculate_end_date
from prozorro.risks.settings import SAS_24_RULES_FROM
from prozorro.risks.utils import get_now

DOC_PUBLISHED_LIMIT_DAYS = 4


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-10"
    owner = "sas24"
    name = (
        "Невідхилення замовником тендерної пропозиції/ пропозиції переможця закупівель у разі "
        "невиконання ним вимог щодо оприлюднення документів"
    )
    description = (
        "Індикатор свідчить про: Невиконання замовником рішення органу оскарження у встановлений законом термін."
    )
    legitimateness = (
        'Підпункт 3 пункту 44 Особливостей № 1178, пункту 3 частини 1 статті 31 Закону України "Про публічні закупівлі"'
    )
    development_basis = (
        'Ознака порушення вимог підпункту 3 пункту 44 Особливостей № 1178, пункту 3 частини 1 статті 31 Закону України '
        '"Про публічні закупівлі" в частині невідхилення замовником тендерної пропозиції/ пропозиції переможця '
        'закупівель, який не надав визначених документів з метою надання йому переваги'
    )
    procurement_methods = (
        "aboveThresholdEU",
        "aboveThresholdUA",
        "aboveThreshold",
    )
    tender_statuses = (
        "active.qualification",
        "active.awarded",
        "complete",
    )
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

    @staticmethod
    def bidder_does_not_have_documents_after_complaint_period(tender, lot=None):
        for award in tender.get("awards", []):
            # Визначаємо наявність Переможця та завершення періоду оскарження щодо рішення про нього.
            if (
                award["status"] == "active"
                and (not lot or lot["id"] == award["lotID"])
                and award.get("complaintPeriod", {}).get("endDate")
                and get_now() > datetime.fromisoformat(award["complaintPeriod"]["endDate"])
            ):
                documents_found = False
                end_date = calculate_end_date(
                    award["date"],
                    timedelta(days=DOC_PUBLISHED_LIMIT_DAYS),
                )
                # Визначаємо наявність довантаження відповідних документів Переможцем
                # за межами строку в 4 дні після його визначення
                for bid in tender.get("bids", []):
                    if bid["id"] == award["bid_id"]:
                        fields = (
                            "documents",
                            "financialDocuments",
                            "eligibilityDocuments",
                            "qualificationDocuments",
                        )
                        for docs_field in fields:
                            for doc in bid.get(docs_field, []):
                                if (
                                    doc.get("datePublished")
                                    and datetime.fromisoformat(doc["datePublished"]) > end_date
                                ):
                                    documents_found = True
                        if not documents_found:
                            return True

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True) and is_winner_awarded(tender):
            if tender.get("lots"):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    if self.bidder_does_not_have_documents_after_complaint_period(tender, lot=lot):
                        return RiskFound()
            else:
                if self.bidder_does_not_have_documents_after_complaint_period(tender):
                    return RiskFound()
        return RiskNotFound()
