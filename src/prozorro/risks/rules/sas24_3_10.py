from datetime import datetime, timedelta

from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import is_winner_awarded, calculate_end_date
from prozorro.risks.settings import (
    SAS_24_RULES_FROM,
    WINNER_AWARDED_DAYS_LIMIT_FOR_OPEN_TENDERS,
)


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
    def bidder_does_not_have_eligibility_documents(tender, lot=None):
        for award in tender.get("awards", []):
            if (
                award["status"] == "active"
                and (not lot or lot["id"] == award["lotID"])
                and is_winner_awarded(tender, award_to_check=award)
            ):
                eligibility_documents_found = False
                end_date = calculate_end_date(
                    award["date"],
                    timedelta(days=WINNER_AWARDED_DAYS_LIMIT_FOR_OPEN_TENDERS),
                )
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
                                    doc.get("documentType") == "eligibilityDocuments"
                                    and doc.get("datePublished")
                                    and datetime.fromisoformat(award["date"])
                                    < datetime.fromisoformat(doc["datePublished"])
                                    < end_date
                                ):
                                    eligibility_documents_found = True
                        if not eligibility_documents_found:
                            return True

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True) and is_winner_awarded(tender):
            if tender.get("lots"):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    if self.bidder_does_not_have_eligibility_documents(tender, lot=lot):
                        return RiskFound()
            else:
                if self.bidder_does_not_have_eligibility_documents(tender):
                    return RiskFound()
        return RiskNotFound()
