import logging
from aiohttp.web import Response
from aiohttp_swagger import swagger_path
from prozorro import version as api_version
from prozorro.risks.db import get_distinct_values, get_risks, find_tenders
from prozorro.risks.serialization import json_response
from prozorro.risks.utils import (
    pagination_params,
    requests_sequence_params,
    requests_params,
)

logger = logging.getLogger(__name__)


@swagger_path("/swagger/ping.yaml")
async def ping_handler(request):
    return Response(text="pong")


@swagger_path("/swagger/version.yaml")
async def get_version(request):
    return json_response({"api_version": api_version})


@swagger_path("/swagger/risks.yaml")
async def get_tender_risks(request, tender_id):
    tender = await get_risks(tender_id)
    return json_response(tender, status=200)


@swagger_path("/swagger/risks_list.yaml")
async def list_tenders(request):
    skip, limit = pagination_params(request)
    result = await find_tenders(
        skip=skip,
        limit=limit,
        **requests_params(request, "sort", "order", "edrpou"),
        **requests_sequence_params(request, "risks", "region", separator=";")
    )
    return result


@swagger_path("/swagger/region_values.yaml")
async def get_region_values(request):
    regions = await get_distinct_values("procuringEntity.address.region")
    result = []
    for region in regions:
        if region:
            result.append(
                {
                    "name": region,
                    "value": region.lower(),
                }
            )
    return json_response(result, status=200)
