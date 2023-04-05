import csv
import io
import logging
import sys

from aiohttp import web
from aiohttp.hdrs import CONTENT_DISPOSITION, CONTENT_TYPE
from aiohttp_swagger import swagger_path
from prozorro import version as api_version
from prozorro.risks.db import (
    build_tender_filters,
    get_distinct_values,
    get_risks,
    get_tender_risks_report,
    find_tenders,
)
from prozorro.risks.serialization import json_response
from prozorro.risks.utils import (
    build_content_disposition_name,
    pagination_params,
    requests_sequence_params,
    requests_params,
)
from prozorro.risks.rules import *  # noqa

logger = logging.getLogger(__name__)
MAX_BUFFER_LINES = 1000


@swagger_path("/swagger/ping.yaml")
async def ping_handler(request):
    return web.Response(text="pong")


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
    try:
        result = await find_tenders(
            skip=skip,
            limit=limit,
            **requests_params(request, "sort", "order", "edrpou"),
            **requests_sequence_params(request, "risks", "region", separator=";"),
        )
    except web.HTTPRequestTimeout as exc:
        return web.Response(text=exc.text, status=exc.status)
    return result


@swagger_path("/swagger/filter_values.yaml")
async def get_filter_values(request):
    regions = await get_distinct_values("procuringEntityRegion")
    risk_modules = sys.modules["prozorro.risks.rules"].__all__
    result = {
        "regions": regions,
        "risk_rules": [risk.removeprefix("risk_").replace("_", "-") for risk in risk_modules],
    }
    return json_response(result, status=200)


@swagger_path("/swagger/download_risks_report.yaml")
async def download_risks_report(request):
    filters = build_tender_filters(
        **requests_params(request, "edrpou"), **requests_sequence_params(request, "risks", "region", separator=";")
    )
    cursor = await get_tender_risks_report(
        filters,
        **requests_params(request, "sort", "order"),
    )
    logger.info(f"Getting tender risks report with parameters: {filters}")
    filename = "Tender_risks_report.csv"

    response = web.StreamResponse()
    response.headers[CONTENT_DISPOSITION] = build_content_disposition_name(filename)
    response.headers[CONTENT_TYPE] = "text/csv"
    await response.prepare(request)

    async def send_buffer():
        await response.write(buffer.getvalue().encode("utf-8"))
        buffer.truncate(0)
        buffer.seek(0)

    field_names = [
        "_id",
        "dateAssessed",
        "dateModified",
        "procuringEntityRegion",
        "procuringEntityEDRPOU",
        "procuringEntityName",
        "valueAmount",
        "valueCurrency",
        "worked_risks",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=field_names, extrasaction="ignore")
    writer.writeheader()
    await send_buffer()

    count = 0
    async for doc in cursor:
        writer.writerow(doc)
        count += 1

        if count > MAX_BUFFER_LINES:
            await send_buffer()
            count = 0

    await send_buffer()
    await response.write_eof()
    return response
