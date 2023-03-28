import aiohttp
import logging
from datetime import datetime
from aiohttp.web_exceptions import HTTPBadRequest
from urllib.parse import quote

from prozorro.risks.exceptions import SkipException
from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.requests import get_object_data
from prozorro.risks.settings import TIMEZONE

logger = logging.getLogger(__name__)

RISKS_METHODS_MAPPING = {
    "tenders": "process_tender",
    "contracts": "process_contract",
}


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


async def process_risks(obj, rules, resource="tenders"):
    """
    Loop for all risk modules in known module path and process provided object

    :param obj: dict Object for processing (could be tender or contract)
    :param rules: list List of RiskRule instances
    :param resource: str Resource that points what kind of objects should be processed
    :return: dict Processed risks for object (e.g. {"worked": [...], "other": [...]})
    """
    risks = {
        "worked": [],
        "other": [],
    }
    for risk_rule in rules:
        process_method = getattr(risk_rule, RISKS_METHODS_MAPPING[resource])
        try:
            risk_indicator = await process_method(obj)
        except SkipException:
            return None
        else:
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


def build_content_disposition_name(file_name):
    try:
        file_name.encode("ascii")
        file_expr = 'filename="{}"'.format(file_name)
    except UnicodeEncodeError:
        file_expr = "filename*=utf-8''{}".format(quote(file_name))
    return f"attachment; {file_expr}"
