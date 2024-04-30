from collections import defaultdict
from datetime import datetime
from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import BaseRiskResult
from prozorro.risks.utils import get_now


RISKS_METHODS_MAPPING = {
    "tenders": "process_tender",
    "contracts": "process_contract",
}


def get_risk_info(item, risk_rule):
    risk = {
        "risk_id": risk_rule.identifier,
        "name": risk_rule.name,
        "owner": risk_rule.owner,
        "description": risk_rule.description,
        "legitimateness": risk_rule.legitimateness,
        "development_basis": risk_rule.development_basis,
        "indicator": item.indicator,
        "date": get_now().isoformat(),
    }
    if item.type != "tender":
        risk["item"] = {
            "id": item.id,
            "type": item.type,
        }
    return risk


async def process_risks(obj, rules, resource="tenders", parent_object=None):
    """
    Loop for all risk modules in known module path and process provided object

    :param obj: dict Object for processing (could be tender or contract)
    :param rules: list List of RiskRule instances
    :param resource: str Resource that points what kind of objects should be processed
    :return: dict Processed risks for object (e.g. {"sas-3-1": {...}, "sas-3-2": {...}})
    """
    risks = defaultdict(list)
    for risk_rule in rules:
        if risk_rule.end_date and get_now().date() >= datetime.strptime(risk_rule.end_date, "%Y-%m-%d").date():
            continue
        if (
            risk_rule.start_date
            and obj.get("dateCreated")
            and datetime.fromisoformat(obj["dateCreated"]).date() < datetime.strptime(
                risk_rule.start_date, "%Y-%m-%d"
            ).date()
        ):
            continue
        process_method = getattr(risk_rule, RISKS_METHODS_MAPPING[resource])
        try:
            risk_result = await process_method(obj, parent_object=parent_object)
        except SkipException:
            continue
        else:
            if isinstance(risk_result, BaseRiskResult):
                risk = get_risk_info(risk_result, risk_rule)
                risks[risk_rule.identifier].append(risk)
            else:
                for item in risk_result:
                    risk = get_risk_info(item, risk_rule)
                    risks[risk_rule.identifier].append(risk)
    return risks
