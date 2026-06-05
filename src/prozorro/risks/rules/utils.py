from datetime import datetime
from dateorro import calc_datetime, calc_normalized_datetime, calc_working_datetime

from prozorro.risks.settings import TEST_MODE, TIMEZONE, WORKING_DAYS


def calculate_end_date(
    date_obj,
    timedelta_obj,
    normalized=True,
    ceil=True,
    working_days=False,
    accelerator=1000,
):
    """
    Calculate end datetime for given date obj depends on timedelta obj.
    For TEST_MODE it will calculate datetime with accelerator 1000 without normalizing.
    Parameters `normalized` and `ceil` are required for calculating datetime from the next day of the week.
    :param date_obj: datetime Datetime object.
    :param timedelta_obj: datetime.timedelta Timedelta object.
    :param normalized: bool Flag for calculating normalized date.
    :param ceil: bool Flag for calculating date from the next day of the week.
    :param working_days: bool Flag for calculating working days, excluding weekends.
    :param accelerator: int Accelerator for calculating datetime in TEST_MODE.
    :return: result datetime object
    """
    date_obj = (
        date_obj if isinstance(date_obj, datetime) else datetime.fromisoformat(date_obj)
    )
    if normalized and TEST_MODE is not True:
        date_obj = calc_normalized_datetime(date_obj, ceil=ceil)
    if working_days:
        result_date_obj = calc_working_datetime(
            date_obj, timedelta_obj, calendar=WORKING_DAYS
        )
    else:
        result_date_obj = calc_datetime(
            date_obj,
            timedelta_obj,
            accelerator=accelerator if TEST_MODE is True else None,
        )

    return TIMEZONE.localize(result_date_obj.replace(tzinfo=None))


def count_percentage_between_two_values(initial_value, delta_value):
    return (initial_value - delta_value) * 100 / initial_value


def get_complaints(obj, statuses=None):
    """
    Return list of complaints in object with status "satisfied" and type "complaint"
    :param obj: dict Object with complaints (can be tender or tender["awards"])
    :param statuses: list Whether complaint should have particular status from the allowed list
    :return: list List of complaints
    """
    complaints = []
    for complaint in obj.get("complaints", []):
        has_status = complaint["status"] in statuses if statuses else True
        if complaint["type"] == "complaint" and has_status:
            complaints.append(complaint)
    return complaints


def flatten(main_list):
    return [item for sublist in main_list for item in sublist]


def is_winner_awarded(tender, award_to_check=None) -> bool:
    """
    Return flag whether tender has already winner.
    :param tender: dict Tender object
    :param award_to_check: dict Award object
    :return: bool Flag awarded or not the winner
    """
    active_awards = (
        [award_to_check]
        if award_to_check
        else [
            award for award in tender.get("awards", []) if award["status"] == "active"
        ]
    )

    return bool(active_awards)


def bidder_applies_on_lot(bid, lot):
    for lot_value in bid.get("lotValues", []):
        if lot_value["relatedLot"] == lot["id"]:
            return True
    return False


def count_winner_disqualifications_and_bidders(tender, lot=None, check_winner=False):
    """
    Count number of winner, disqualifications and bidders in tender.
    :param tender: Tender object
    :param lot: Lot object. If not specified, there will be no lotId connection checks in award and bidder.
    :param check_winner: Flag whether winner should be checked with special condition
    :return: set of winner, disqualifications and bidders count
    """
    disqualified_awards = set()
    winner_count = 0
    bidders = set()
    for award in tender.get("awards", []):
        # Перевіряється кількість дискваліфікацій - наявність в процедурі
        # унікальних об’єктів data.awards (конкатенація data.awards.suppliers.identifier.scheme
        # та data.awards.suppliers.identifier.id), де data.awards.status = 'unsuccessful'.
        if award["status"] == "unsuccessful" and (
            not lot or award.get("lotID") == lot["id"]
        ):
            for supplier in award.get("suppliers", []):
                disqualified_awards.add(
                    f"{supplier['identifier']['scheme']}-{supplier['identifier']['id']}"
                )
        # Перевіряється наявність в процедурі data.awards, де data.awards.status = 'active'.
        elif (
            award["status"] == "active"
            and (not lot or award.get("lotID") == lot["id"])
            and (not check_winner or is_winner_awarded(tender, award_to_check=award))
        ):
            winner_count = 1
    disqualifications_count = len(disqualified_awards)
    # Перевіряється кількість учасників - в процедурі кількість
    # унікальних об’єктів data.bids (конкатенація data.bids.tenderers.identifier.scheme
    # та data.bids.tenderers.identifier.id), де data.bids.status = 'active'.
    for bid in tender.get("bids", []):
        if bid["status"] == "active" and (not lot or bidder_applies_on_lot(bid, lot)):
            for tenderer in bid.get("tenderers", []):
                bidders.add(
                    f"{tenderer['identifier']['scheme']}-{tenderer['identifier']['id']}"
                )
    bidders_count = len(bidders)
    return disqualifications_count, winner_count, bidders_count


def has_milestone_24(obj):
    """
    Check if obj has milestone with code 24 hours.
    :param obj: dict Object
    :return: Flag whether object has milestone with code 24h.
    """
    for milestone in obj.get("milestones", []):
        if milestone["code"] == "24h":
            return True
    return False
