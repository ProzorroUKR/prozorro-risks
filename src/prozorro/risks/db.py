import asyncio
import logging
from contextvars import ContextVar
from motor.motor_asyncio import AsyncIOMotorClient
from prozorro.risks.settings import (
    MONGODB_URL,
    DB_NAME,
    READ_PREFERENCE,
    WRITE_CONCERN,
    READ_CONCERN,
    MAX_LIST_LIMIT,
)
from prozorro.risks.models import PaginatedList
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import PyMongoError
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
    region_index = IndexModel([("procuringEntityRegion", ASCENDING)], background=True)
    value_index = IndexModel([("value.amount", ASCENDING)], background=True)
    date_modified_index = IndexModel([("dateModified", ASCENDING)], background=True)
    risks_worked_index = IndexModel([("risks.worked.id", ASCENDING)], background=True)

    try:
        await get_risks_collection().create_indexes(
            [region_index, value_index, date_modified_index, risks_worked_index]
        )
    except PyMongoError as e:
        logger.exception(e)


async def init_tender_indexes():
    compound_procuring_entity_index = IndexModel(
        [
            ("procuringEntityIdentifier", ASCENDING),
            ("dateCreated", DESCENDING),
            ("procurementMethodType", ASCENDING),
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
        result = await collection.find_one({"_id": tender_id})
    except PyMongoError as e:
        logger.error(f"Get tender {type(e)}: {e}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        raise web.HTTPInternalServerError()
    else:
        if not result:
            raise web.HTTPNotFound()
        return result


def _build_tender_filters(**kwargs):
    filters = {}
    if risks_list := kwargs.get("risks"):
        filters["risks.worked"] = {"$elemMatch": {"id": {"$in": risks_list}}}
    if region := kwargs.get("region"):
        filters["procuringEntityRegion"] = {"$regex": rf"^{region.lower()}"}
    return filters


async def find_tenders(skip=0, limit=20, **kwargs):
    collection = get_risks_collection()
    limit = min(limit, MAX_LIST_LIMIT)
    filters = _build_tender_filters(**kwargs)
    request_sort = kwargs.get("sort")
    sort_field = request_sort if request_sort else "dateModified"
    sort_order = ASCENDING if kwargs.get("order") == "asc" else DESCENDING
    result = await paginated_result(
        collection,
        filters,
        skip,
        limit,
        sort=[(sort_field, sort_order)],
        projection={"procuringEntityRegion": False},
    )
    return result


async def update_tender_risks(uid, updated_fields):
    await get_risks_collection().update_one(
        {"_id": uid},
        {"$set": updated_fields},
        upsert=True,
        session=session_var.get(),
    )


async def save_tender(uid, tender_data):
    await get_tenders_collection().find_one_and_update(
        {"_id": uid},
        {"$set": tender_data},
        upsert=True,
        session=session_var.get(),
    )


async def paginated_result(collection, filters, skip, limit, sort=None, projection=None):
    limit = min(limit, MAX_LIST_LIMIT)
    count = await collection.count_documents(filters)
    cursor = collection.find(filters, projection=projection).skip(skip).limit(limit)
    if sort:
        cursor = cursor.sort(sort)
    return PaginatedList(items=cursor, count=count)


async def get_distinct_values(field):
    return await get_risks_collection().distinct(field)


async def aggregate_tenders(pipeline):
    cursor = get_tenders_collection().aggregate(pipeline)
    aggregate_response = await cursor.to_list(length=None)
    try:
        result = aggregate_response[0]
    except IndexError:
        result = dict()
    return result
