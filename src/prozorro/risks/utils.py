import logging
from datetime import datetime
from aiohttp.web_exceptions import HTTPBadRequest
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
