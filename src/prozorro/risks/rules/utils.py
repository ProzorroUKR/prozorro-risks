from datetime import datetime


def count_days_between_two_dates(date_1, date_2):
    date_1 = date_1 if isinstance(date_1, datetime) else datetime.fromisoformat(date_1)
    date_2 = date_2 if isinstance(date_2, datetime) else datetime.fromisoformat(date_2)
    return (date_1.date() - date_2.date()).days


def count_percentage_between_two_values(initial_value, delta_value):
    return (initial_value - delta_value) * 100 / initial_value


def get_satisfied_complaints(obj):
    """
    Return list of complaints in object with status "satisfied" and type "complaint"
    :param obj: dict Object with complaints (can be tender or tender["awards"])
    :return: list List of complaints
    """
    complaints = []
    for complaint in obj.get("complaints", []):
        if complaint["type"] == "complaint" and complaint["status"] == "satisfied":
            complaints.append(complaint)
    return complaints


def flatten(main_list):
    return [item for sublist in main_list for item in sublist]
