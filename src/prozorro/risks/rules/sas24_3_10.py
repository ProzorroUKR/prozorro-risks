from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import is_winner_awarded
from prozorro.risks.settings import SAS_24_RULES_FROM


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
    def check_eligibility_documents_for_bidder(tender, lot=None):
        for award in tender.get("awards", []):
            if (
                award["status"] == "active"
                and (not lot or lot["id"] == award["lotID"])
                and is_winner_awarded(tender, award_to_check=award)
            ):
                for bid in tender.get("bids", []):
                    if bid["id"] == award["bid_id"]:
                        fields = ("documents", "financialDocuments", "eligibilityDocuments", "qualificationDocuments")
                        for docs_field in fields:
                            for doc in bid.get(docs_field, []):
                                if doc.get("documentType") == "eligibilityDocuments":
                                    return RiskNotFound()
                        return RiskFound()
        return RiskNotFound()

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(tender, category=False, value=True) and is_winner_awarded(tender):
            if tender.get("lots"):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    return self.check_eligibility_documents_for_bidder(tender, lot=lot)
            else:
                return self.check_eligibility_documents_for_bidder(tender)
        return RiskNotFound()
