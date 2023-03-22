import aiohttp
import logging
import sys
from datetime import datetime
from aiohttp.web_exceptions import HTTPBadRequest

from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.requests import get_object_data
from prozorro.risks.settings import TIMEZONE


logger = logging.getLogger(__name__)


def get_now() -> datetime:
    return datetime.now(TIMEZONE)


def get_int_from_query(request, key, default=0):
    value = request.query.get(key, default)
    try:
        value = int(value)
    except ValueError as e:
        logger.exception(e)
        raise HTTPBadRequest(text=f"Can't parse {key} from value: '{value}'")
    else:
        return value


def pagination_params(request, default_limit=20):
    skip = get_int_from_query(request, "skip")
    limit = get_int_from_query(request, "limit", default=default_limit)
    return skip, limit


def requests_params(request, *args):
    params = {}
    for param in args:
        params[param] = request.query.get(param)
    return params


def requests_sequence_params(request, *args, separator=None):
    params = {}
    for param in args:
        value = request.query.get(param)
        if value:
            params[param] = value.split("," if not separator else separator)
    return params


async def fetch_tender(tender_id):
    """
    Get tender from database if it can be found or fetch from API
    :param tender_id:
    :return:
    """
    from prozorro.risks.db import get_tender

    tender = await get_tender(tender_id)
    if not tender:
        async with aiohttp.ClientSession() as session:
            tender = await get_object_data(session, tender_id)
    return tender


async def process_risks(module_path, obj):
    """
    Loop for all risk modules in known module path and process provided object

    :param module_path: str Path to risk module
    :param obj: dict Object for processing (could be tender or contract)
    :return: dict Processed risks for object (e.g. {"worked": [...], "other": [...]})
    """
    risk_modules = sys.modules[module_path].__all__
    risks = {
        "worked": [],
        "other": [],
    }
    for module_name in risk_modules:
        risk_module = getattr(sys.modules[module_path], module_name)
        risk_rule = getattr(risk_module, "RiskRule")()
        risk_indicator = await risk_rule.process_tender(obj)
        if risk_indicator == RiskIndicatorEnum.risk_found:
            risks["worked"].append(
                {
                    "id": risk_rule.identifier,
                    "name": risk_rule.name,
                    "description": risk_rule.description,
                    "legitimateness": risk_rule.legitimateness,
                    "development_basis": risk_rule.development_basis,
                    "indicator": risk_indicator,
                    "date": get_now().isoformat(),
                }
            )
        else:
            risks["other"].append(
                {
                    "id": risk_rule.identifier,
                    "indicator": risk_indicator,
                    "date": get_now().isoformat(),
                }
            )
    return risks
