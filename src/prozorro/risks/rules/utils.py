from datetime import datetime


def count_days_between_two_dates(date_1, date_2):
    date_1 = date_1 if isinstance(date_1, datetime) else datetime.fromisoformat(date_1)
    date_2 = date_2 if isinstance(date_2, datetime) else datetime.fromisoformat(date_2)
    return (date_1.date() - date_2.date()).days
