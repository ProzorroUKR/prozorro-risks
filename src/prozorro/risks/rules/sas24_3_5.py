from prozorro.risks.models import RiskFound, RiskNotFound
from prozorro.risks.rules.base import BaseTenderRiskRule
from prozorro.risks.rules.utils import (
    is_winner_awarded,
    count_winner_disqualifications_and_bidders,
)
from prozorro.risks.settings import SAS_24_RULES_FROM


class RiskRule(BaseTenderRiskRule):
    identifier = "sas24-3-5"
    owner = "sas24"
    name = "Замовник відхилив мінімум 2 учасників"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник відхиляє мінімум 2 учасників"
    )
    legitimateness = (
        "Порушення принципів здійснення закупівель, що викладені у статті 5 Закону України 'Про публічні закупівлі'."
    )
    development_basis = "Цей індикатор було розроблено для виявлення ознак змови замовника з постачальником(ками)."
    procurement_methods = ("aboveThresholdEU", "aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded", "complete")
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
    def has_milestone_24(obj):
        for milestone in obj.get("milestones", []):
            if milestone["code"] == "24h":
                return True
        return False

    async def process_tender(self, tender, parent_object=None):
        if self.tender_matches_requirements(
            tender, category=False, value=True
        ) and is_winner_awarded(tender):
            open_eu_tender = tender["procurementMethodType"] == "aboveThresholdEU"
            # Визначаємо кількість дискваліфікацій
            unsuccessful_awards = [
                aw
                for aw in tender.get("awards", [])
                if aw["status"] == "unsuccessful" and not self.has_milestone_24(aw)
            ]

            unsuccessful_qualifications = [
                qual
                for qual in tender.get("qualifications", [])
                if qual["status"] == "unsuccessful" and not self.has_milestone_24(qual)
            ]

            if open_eu_tender:
                if not unsuccessful_qualifications:
                    return RiskNotFound()
            elif not unsuccessful_awards:
                return RiskNotFound()

            if len(tender.get("lots", [])):
                for lot in tender["lots"]:
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    disqualified_bidders_in_qualif = set()

                    # Визначаємо кількість дискваліфікацій для aboveThresholdEU - qualifications.status = 'unsuccessful'
                    if open_eu_tender:
                        for qualification in unsuccessful_qualifications:
                            if qualification.get("lotID") == lot["id"]:
                                disqualified_bidders_in_qualif.add(
                                    qualification["bidID"]
                                )

                    # Визначаємо кількість дискваліфікацій - кількість об’єктів data.awards, що посилаються
                    # на лот data.awards.lotID=data.lots.id та мають data.awards.status='unsuccessful'
                    disqualified_lots_count_in_qualif, winner_count, _ = (
                        count_winner_disqualifications_and_bidders(
                            tender,
                            lot,
                            check_winner=True,
                        )
                    )

                    # Якщо кількість дискваліфікацій дорівнює 2 або більше, індикатор приймає значення 1
                    if winner_count and (
                        disqualified_lots_count_in_qualif >= 2
                        or len(disqualified_bidders_in_qualif) >= 2
                    ):
                        return RiskFound()
            else:
                # Якщо процедура не має лотів i кількість дискваліфікацій дорівнює 2 або більше,
                # індикатор приймає значення 1
                disqualifications_count, winner_count, _ = (
                    count_winner_disqualifications_and_bidders(
                        tender,
                        check_winner=True,
                    )
                )
                if winner_count and (
                    (open_eu_tender and len(unsuccessful_qualifications) >= 2)
                    or disqualifications_count >= 2
                ):
                    return RiskFound()
        return RiskNotFound()
