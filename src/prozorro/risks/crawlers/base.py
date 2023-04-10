from datetime import datetime
from prozorro.risks.exceptions import SkipException
from prozorro.risks.utils import get_now


RISKS_METHODS_MAPPING = {
    "tenders": "process_tender",
    "contracts": "process_contract",
}


async def process_risks(obj, rules, resource="tenders"):
    """
    Loop for all risk modules in known module path and process provided object

    :param obj: dict Object for processing (could be tender or contract)
    :param rules: list List of RiskRule instances
    :param resource: str Resource that points what kind of objects should be processed
    :return: dict Processed risks for object (e.g. {"sas-3-1": {...}, "sas-3-2": {...}})
    """
    risks = {}
    for risk_rule in rules:
        if risk_rule.end_date and get_now().date() >= datetime.strptime(risk_rule.end_date, "%Y-%m-%d").date():
            break
        process_method = getattr(risk_rule, RISKS_METHODS_MAPPING[resource])
        try:
            risk_indicator = await process_method(obj)
        except SkipException:
            return None
        else:
            risks[risk_rule.identifier] = {
                "name": risk_rule.name,
                "description": risk_rule.description,
                "legitimateness": risk_rule.legitimateness,
                "development_basis": risk_rule.development_basis,
                "indicator": risk_indicator,
                "date": get_now().isoformat(),
            }
    return risks
