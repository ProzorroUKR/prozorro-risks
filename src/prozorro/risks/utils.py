import aiohttp
import logging
from datetime import datetime

import pytz
from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest
from urllib.parse import quote, urlencode
from ciso8601 import parse_datetime

from prozorro.risks.requests import get_object_data
from prozorro.risks.settings import ALLOW_ALL_ORIGINS, TIMEZONE, HTTPS_PROXY

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


def build_content_disposition_name(file_name):
    try:
        file_name.encode("ascii")
        file_expr = 'filename="{}"'.format(file_name)
    except UnicodeEncodeError:
        file_expr = "filename*=utf-8''{}".format(quote(file_name))
    return f"attachment; {file_expr}"


def build_headers_for_fixing_cors(request, response):
    if ALLOW_ALL_ORIGINS and isinstance(response, web.StreamResponse):
        # fixes cors preflight OPTIONS requests
        if request.method == "OPTIONS" and response.status in (401, 405):
            response = web.StreamResponse()

        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "")
        response.headers["Access-Control-Allow-Credentials"] = "true"

        allow_methods = request.headers.get("Access-Control-Request-Method")
        if allow_methods:
            response.headers["Access-Control-Allow-Methods"] = allow_methods

        req_headers = request.headers.get("Access-Control-Request-Headers")
        if req_headers:
            response.headers["Access-Control-Allow-Headers"] = req_headers.upper()


def get_page(request, params):
    base_url = f"{request.scheme}://{request.host}"
    next_path = f"{request.path}?{urlencode(params)}"
    return {
        "offset": params.get("offset", ""),
        "path": next_path,
        "uri": f"{base_url}{next_path}",
    }


def parse_offset(offset: str):
    try:
        # Use offset in timestamp format
        offset_timestamp = float(offset)
        date = datetime.fromtimestamp(offset_timestamp)
    except ValueError:
        # Use offset in iso format
        date = parse_datetime(offset)
    if not date.tzinfo:
        date = pytz.utc.localize(date)
    return date.isoformat()


def tender_created_after_release(tender, release_date, date_format="%Y-%m-%d"):
    return (
        tender.get("dateCreated")
        and datetime.fromisoformat(tender["dateCreated"]).date() >= datetime.strptime(release_date, date_format).date()
    )


def tender_should_be_checked_for_termination(tender):
    """
    As we reload crawler in past date and check once again all tenders,
    we need to check and refresh terminated flag for already completed tenders, as they can have active contracts.
    :param tender: dict of tender info
    :return: flag whether tender should be checked for termination
    """
    return tender.get("status") == "complete" and tender.get("procurementMethodType") in (
        "negotiation",
        "negotiation.quick",
        "aboveThresholdUA",
        "aboveThresholdEU",
        "aboveThreshold",
        "belowThreshold",
        "reporting",
    )  # pmt for contract risks


def get_subject_of_procurement(tender_obj):
    """
    Get subject of procurement for tender.
    Find parent code for tender, see logic here:
    https://dasu-indicators-docs.readthedocs.io/en/latest/tv_subjectOfProcurement.html#tv-subjectofprocurement
    :param tender_obj: dict of tender info
    :return: string subject of procurement
    """
    items_cpvs = [item["classification"]["id"][:-2].rstrip("0") for item in tender_obj["items"]]
    uniq_cpvs = set(items_cpvs)
    cpvs = sorted(uniq_cpvs, key=len)
    parent_cpv_found = False
    prefix_length = len(cpvs[0])
    while parent_cpv_found is False:
        for cpv in cpvs:
            if cpv[:prefix_length] != cpvs[0][:prefix_length]:
                prefix_length -= 1
                break
        else:
            parent_cpv_found = True
    code = cpvs[0][:prefix_length]
    if code.startswith("45"):
        if len(code) > 5:
            code = code[:5]
    elif code.startswith(("3361", "3362", "3363", "3364", "3365", "3366", "3367", "33691", "33692")):
        if len(code) > 3:
            code = code[:3]
    elif len(code) > 4:
        code = code[:4]
    return code


async def get_exchanged_value(obj, date):
    if obj.get("value", {}).get("amount") and obj["value"].get("currency") and obj["value"]["currency"] != "UAH":
        uid = obj.get("id" if "id" in obj else "_id")
        async with aiohttp.ClientSession() as session:
            kwargs = {}
            if HTTPS_PROXY:
                kwargs.update(proxy=HTTPS_PROXY)
            rates = await get_object_data(
                session,
                uid,
                resource="NBU",
                date=datetime.fromisoformat(date).strftime('%Y%m%d'),
                **kwargs,
            )
        for rate in rates:
            if rate["cc"] == obj["value"]["currency"]:
                return obj["value"]["amount"] * rate["rate"]
    return obj.get("value", {}).get("amount", 0)
