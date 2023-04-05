from prozorro.risks.logging import request_id_var
from prozorro.risks.serialization import json_response
from prozorro.risks.utils import build_headers_for_fixing_cors
from aiohttp.web import middleware
from uuid import uuid4
import logging


logger = logging.getLogger(__name__)


@middleware
async def request_id_middleware(request, handler):
    """
    Sets request_id contextvar and request['request_id']
    :param request:
    :param handler:
    :return:
    """
    value = request.headers.get("X-Request-ID", str(uuid4()))
    request_id_var.set(value)  # for loggers inside context
    response = await handler(request)
    response.headers["X-Request-ID"] = value  # for AccessLogger
    return response


@middleware
async def request_unpack_params(request, handler):
    """
    middleware for the func views
    to pass variables from url
    as kwargs
    """
    if "swagger" in request.path:
        return await handler(request)
    return await handler(request, **request.match_info)


@middleware
async def convert_response_to_json(request, handler):
    """
    Convert dicts into valid json responses
    """
    response = await handler(request)
    if isinstance(response, dict):
        status_code = 201 if request.method == "POST" else 200
        response = json_response(response, status=status_code)
    return response


@middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    build_headers_for_fixing_cors(request, response)
    return response
