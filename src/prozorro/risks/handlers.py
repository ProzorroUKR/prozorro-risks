import csv
import io
import logging
import sys

from aiohttp import web
from aiohttp.hdrs import CONTENT_DISPOSITION, CONTENT_TYPE
from aiohttp_swagger import swagger_path
from datetime import datetime
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
    get_now,
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
            **requests_params(request, "sort", "order", "edrpou", "tender_id"),
            **requests_sequence_params(request, "risks", "region", "owner", separator=";"),
        )
    except web.HTTPRequestTimeout as exc:
        return web.Response(text=exc.text, status=exc.status)
    return result


@swagger_path("/swagger/filter_values.yaml")
async def get_filter_values(request):
    regions = await get_distinct_values("procuringEntityRegion")
    risk_rules = []
    risk_rule_module = sys.modules["prozorro.risks.rules"]
    for module_name in risk_rule_module.__all__:
        risk_module = getattr(risk_rule_module, module_name)
        risk_rule = getattr(risk_module, "RiskRule")()
        risk_rules.append(
            {
                "identifier": risk_rule.identifier,
                "start_date": risk_rule.start_date,
                "end_date": risk_rule.end_date,
                "status": "archived"
                if risk_rule.end_date and get_now().date() >= datetime.strptime(risk_rule.end_date, "%Y-%m-%d").date()
                else "active",
            }
        )
    result = {
        "regions": regions,
        "risk_rules": risk_rules,
    }
    return json_response(result, status=200)


@swagger_path("/swagger/download_risks_report.yaml")
async def download_risks_report(request):
    filters = build_tender_filters(
        **requests_params(request, "edrpou", "tender_id"),
        **requests_sequence_params(request, "risks", "region", separator=";"),
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
