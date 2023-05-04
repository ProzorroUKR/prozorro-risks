from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.rules.base import BaseTenderRiskRule


class RiskRule(BaseTenderRiskRule):
    identifier = "sas-3-2"
    name = "Замовник відхилив тендерні пропозиції всіх учасників під час закупівлі товарів або послуг, крім переможця"
    description = (
        "Даний індикатор виявляє ситуації, коли замовник дискваліфікував усіх учасників лота або процедури "
        "(якщо вона однолотова), окрім переможця."
    )
    legitimateness = ""
    development_basis = "Цей індикатор було розроблено, щоб виявляти можливі змови Замовника з Учасником."
    procurement_methods = ("aboveThresholdUA", "aboveThreshold")
    tender_statuses = ("active.qualification", "active.awarded")
    procuring_entity_kinds = (
        "authority",
        "central",
        "general",
        "social",
        "special",
    )
    procurement_categories = ("goods", "services")

    @staticmethod
    def bidder_applies_on_lot(bid, lot):
        for lot_value in bid.get("lotValues", []):
            if lot_value["relatedLot"] == lot["id"]:
                return True
        return False

    async def process_tender(self, tender):
        if self.tender_matches_requirements(tender):
            if len(tender.get("lots", [])):
                for lot in tender.get("lots", []):
                    if lot["status"] in ("cancelled", "unsuccessful"):
                        continue
                    disqualified_awards = set()
                    winner_count = 0
                    bidders = set()
                    for award in tender.get("awards", []):
                        # Для лота (data.lots.id) перевіряється кількість дискваліфікацій - наявність в процедурі
                        # унікальних об’єктів data.awards (конкатенація data.awards.suppliers.identifier.scheme
                        # та data.awards.suppliers.identifier.id), де data.awards.status = 'unsuccessful',
                        # що посилаються на лот по data.awards.lotID = data.lots.id.
                        # Кількість таких об’єктів заноситься у поле “Дискваліфікації”.
                        if award.get("lotID") == lot["id"] and award["status"] == "unsuccessful":
                            for supplier in award.get("suppliers", []):
                                disqualified_awards.add(
                                    f'{supplier["identifier"]["scheme"]}-{supplier["identifier"]["id"]}'
                                )
                        # Перевіряється наявність в процедурі data.awards, де data.awards.status = 'active',
                        # що посилається на лот по data.awards.lotID = data.lots.id.
                        # Таким чином “Переможець” для лота дорівнює “1”.
                        elif award["lotID"] == lot["id"] and award["status"] == "active":
                            winner_count = 1

                    if not disqualified_awards or not winner_count:
                        continue

                    disqualifications_count = len(disqualified_awards)
                    if disqualifications_count <= 2:
                        continue

                    # Для кожного лота (data.lots.id) перевіряється кількість учасників - в процедурі кількість
                    # унікальних об’єктів data.bids (конкатенація data.bids.tenderers.identifier.scheme
                    # та data.bids.tenderers.identifier.id), де data.bids.status = 'active',
                    # що посилаються на лот по data.bids.lotValues.relatedLot = data.lots.id.
                    # Кількість таких об’єктів заноситься у поле “Учасники”.
                    for bid in tender.get("bids", []):
                        if bid["status"] == "active" and self.bidder_applies_on_lot(bid, lot):
                            for tenderer in bid.get("tenderers", []):
                                bidders.add(f'{tenderer["identifier"]["scheme"]}-{tenderer["identifier"]["id"]}')
                    bidders_count = len(bidders)

                    # Якщо для лота “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”.
                    if bidders_count == winner_count + disqualifications_count:
                        return RiskIndicatorEnum.risk_found
            else:
                disqualified_awards = set()
                winner_count = 0
                bidders = set()
                for award in tender.get("awards", []):
                    # Для тендера перевіряється кількість дискваліфікацій - наявність в процедурі унікальних об’єктів
                    # data.awards (конкатенація data.awards.suppliers.identifier.scheme та
                    # data.awards.suppliers.identifier.id), де data.awards.status = 'unsuccessful'.
                    # Кількість таких об’єктів заноситься у поле “Дискваліфікації”
                    if award["status"] == "unsuccessful":
                        for supplier in award.get("suppliers", []):
                            disqualified_awards.add(
                                f'{supplier["identifier"]["scheme"]}-{supplier["identifier"]["id"]}'
                            )
                    # Перевіряється наявність в процедурі data.id об’єкта data.awards, де data.awards.status = 'active'.
                    # Таким чином “Переможець” для лота дорівнює “1”.
                    elif award["status"] == "active":
                        winner_count = 1

                if not disqualified_awards or not winner_count:
                    return RiskIndicatorEnum.risk_not_found

                disqualifications_count = len(disqualified_awards)
                # Якщо кількість таких об’єктів менше або дорівнює 2, то індикатор дорівнює “0”
                if disqualifications_count <= 2:
                    return RiskIndicatorEnum.risk_not_found

                # Перевіряється кількість учасників - в процедурі data.id кількість унікальних об’єктів data.bids
                # (конкатенація data.bids.tenderers.identifier.scheme та data.bids.tenderers.identifier.id),
                # де data.bids.status = 'active'. Кількість таких об’єктів заноситься у поле “Учасники”.
                for bid in tender.get("bids", []):
                    if bid["status"] == "active":
                        for tenderer in bid.get("tenderers", []):
                            bidders.add(f'{tenderer["identifier"]["scheme"]}-{tenderer["identifier"]["id"]}')
                bidders_count = len(bidders)

                # Якщо “Учасники” = “Переможець” + “Дискваліфікації”, індикатор приймає значення “1”
                if bidders_count == winner_count + disqualifications_count:
                    return RiskIndicatorEnum.risk_found
        elif tender.get("status") == self.stop_assessment_status:
            return RiskIndicatorEnum.use_previous_result
        return RiskIndicatorEnum.risk_not_found
