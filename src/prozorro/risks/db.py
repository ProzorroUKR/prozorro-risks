import asyncio
import logging
from contextvars import ContextVar
from motor.motor_asyncio import AsyncIOMotorClient
from prozorro.risks.settings import (
    MONGODB_URL,
    DB_NAME,
    READ_PREFERENCE,
    REPORT_ITEMS_LIMIT,
    WRITE_CONCERN,
    READ_CONCERN,
    MAX_LIST_LIMIT,
    MAX_TIME_QUERY,
    MONGODB_ERROR_INTERVAL,
)
from prozorro.risks.models import RiskIndicatorEnum
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import ExecutionTimeout, PyMongoError
from aiohttp import web

logger = logging.getLogger(__name__)

DB = None
session_var = ContextVar("session", default=None)


def get_database():
    return DB


async def init_mongodb(*_):
    global DB
    logger.info("Init mongodb instance")
    loop = asyncio.get_event_loop()
    conn = AsyncIOMotorClient(MONGODB_URL, io_loop=loop)
    DB = conn.get_database(
        DB_NAME,
        read_preference=READ_PREFERENCE,
        write_concern=WRITE_CONCERN,
        read_concern=READ_CONCERN,
    )
    await asyncio.gather(
        init_risks_indexes(),
        init_tender_indexes(),
    )
    return DB


async def cleanup_db_client(*_):
    global DB
    if DB:
        DB.client.close()
        DB = None


async def flush_database(*_):
    await asyncio.gather(
        get_risks_collection().delete_many({}),
        get_tenders_collection().delete_many({}),
    )


def get_risks_collection():
    return DB.risks


def get_tenders_collection():
    return DB.tenders


async def init_risks_indexes():
    region_compound_index = IndexModel(
        [
            ("procuringEntityRegion", ASCENDING),
            ("worked_risks", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
    )
    edrpou_compound_with_date_index = IndexModel(
        [
            ("procuringEntityEDRPOU", ASCENDING),
            ("worked_risks", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
    )
    date_assessed_index = IndexModel([("dateAssessed", ASCENDING)], background=True)
    value_amount_index = IndexModel([("value.amount", ASCENDING)], background=True)
    risks_worked_index = IndexModel(
        [
            ("worked_risks", ASCENDING),
            ("value.amount", ASCENDING),
        ],
        background=True,
    )

    try:
        await get_risks_collection().create_indexes(
            [
                region_compound_index,
                edrpou_compound_with_date_index,
                date_assessed_index,
                value_amount_index,
                risks_worked_index,
            ]
        )
    except PyMongoError as e:
        logger.exception(e)


async def init_tender_indexes():
    compound_procuring_entity_index = IndexModel(
        [
            ("procuringEntityIdentifier", ASCENDING),
            ("contracts.dateSigned", DESCENDING),
        ],
        background=True,
    )
    try:
        await get_tenders_collection().create_indexes([compound_procuring_entity_index])
    except PyMongoError as e:
        logger.exception(e)


async def get_risks(tender_id):
    collection = get_risks_collection()
    try:
        result = await collection.find_one(
            {"_id": tender_id},
            projection={
                "procuringEntityRegion": False,
                "procuringEntityEDRPOU": False,
                "worked_risks": False,
            },
        )
    except PyMongoError as e:
        logger.error(f"Get tender {type(e)}: {e}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        raise web.HTTPInternalServerError()
    else:
        if not result:
            raise web.HTTPNotFound()
        return result


def build_tender_filters(**kwargs):
    filters = {}
    if tender_id := kwargs.get("tender_id"):
        filters["_id"] = tender_id
    if regions_list := kwargs.get("region"):
        filters["procuringEntityRegion"] = {"$in": regions_list}
    if edrpou := kwargs.get("edrpou"):
        filters["procuringEntityEDRPOU"] = edrpou
    if risks_list := kwargs.get("risks"):
        filters["worked_risks"] = {"$in": risks_list}
    return filters


async def find_tenders(skip=0, limit=20, **kwargs):
    collection = get_risks_collection()
    limit = min(limit, MAX_LIST_LIMIT)
    filters = build_tender_filters(**kwargs)
    request_sort = kwargs.get("sort")
    sort_field = request_sort if request_sort else "dateAssessed"
    sort_order = ASCENDING if kwargs.get("order") == "asc" else DESCENDING
    result = await paginated_result(
        collection,
        filters,
        skip,
        limit,
        sort=[(sort_field, sort_order)],
        projection={
            "procuringEntityRegion": False,
            "procuringEntityEDRPOU": False,
            "worked_risks": False,
        },
    )
    return result


def join_old_risks_with_new_ones(risks, tender):
    tender_risks = tender.get("risks", {})
    tender_worked_risks = set(tender.get("worked_risks", []))
    for risk_id, risk_data in risks.items():
        log = {"date": risk_data["date"], "indicator": risk_data["indicator"]}
        history = tender_risks.get(risk_id, {}).get("history", [])
        history.append(log)
        risks[risk_id]["history"] = history
        if risk_data["indicator"] == RiskIndicatorEnum.risk_found:
            tender_worked_risks.add(risk_id)
        elif risk_id in tender_worked_risks:
            tender_worked_risks.remove(risk_id)
    tender_risks.update(risks)
    return tender_risks, list(tender_worked_risks)


async def update_tender_risks(uid, risks, additional_fields):
    filters = {"_id": uid}
    while True:
        try:
            tender = await get_risks_collection().find_one({"_id": uid})
            risks, worked_risks = join_old_risks_with_new_ones(risks, tender if tender else {})
            if tender:
                filters["dateAssessed"] = tender.get("dateAssessed")
            result = await get_risks_collection().find_one_and_update(
                filters,
                {
                    "$set": {
                        "_id": uid,
                        "risks": risks,
                        "worked_risks": worked_risks,
                        **additional_fields,
                    },
                },
                upsert=True,
                session=session_var.get(),
            )
        except PyMongoError as e:
            logger.warning(f"Update risks error {type(e)}: {e}", extra={"MESSAGE_ID": "MONGODB_EXC"})
            await asyncio.sleep(MONGODB_ERROR_INTERVAL)
        else:
            return result


async def save_tender(uid, tender_data):
    await get_tenders_collection().find_one_and_update(
        {"_id": uid},
        {"$set": tender_data},
        upsert=True,
        session=session_var.get(),
    )


async def paginated_result(collection, filters, skip, limit, sort=None, projection=None):
    try:
        count = await collection.count_documents(filters, maxTimeMS=MAX_TIME_QUERY)
        cursor = collection.find(filters, projection=projection, max_time_ms=MAX_TIME_QUERY).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        items = await cursor.to_list(length=None)
    except ExecutionTimeout as exc:
        logger.error(f"Filter tenders {type(exc)}: {exc}, filters: {filters}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        raise web.HTTPRequestTimeout(text="Please change filters combination to optimize query (e.g. edrpou + risks)")
    return dict(items=items, count=count)


async def get_distinct_values(field):
    return await get_risks_collection().distinct(field, {field: {"$nin": ["", None]}})


async def aggregate_tenders(pipeline):
    cursor = get_tenders_collection().aggregate(pipeline)
    aggregate_response = await cursor.to_list(length=None)
    try:
        result = aggregate_response[0]
    except IndexError:
        result = dict()
    return result


async def get_tender(tender_id):
    collection = get_tenders_collection()
    while True:
        try:
            result = await collection.find_one({"_id": tender_id})
        except PyMongoError as e:
            logger.error(f"Get tender {type(e)}: {e}", extra={"MESSAGE_ID": "MONGODB_EXC"})
            await asyncio.sleep(MONGODB_ERROR_INTERVAL)
        else:
            return result


async def get_tender_risks_report(filters, **kwargs):
    collection = get_risks_collection()
    request_sort = kwargs.get("sort")
    sort_field = request_sort if request_sort else "dateAssessed"
    sort_order = ASCENDING if kwargs.get("order") == "asc" else DESCENDING
    pipeline = [
        {"$match": filters},
        {"$sort": {sort_field: sort_order, "_id": 1}},  # including _id field guarantee sort consistency during limit
        {"$limit": REPORT_ITEMS_LIMIT},
        {
            "$addFields": {
                "procuringEntityName": "$procuringEntity.name",
                "valueAmount": "$value.amount",
                "valueCurrency": "$value.currency",
            }
        },
    ]
    #  allowDiskUse = True allow writing temporary files on disk when a pipeline stage exceeds the 100 megabyte limit
    cursor = collection.aggregate(pipeline, allowDiskUse=True, maxTimeMS=MAX_TIME_QUERY)
    return cursor
