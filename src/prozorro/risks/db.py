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
    MAX_TIME_QUERY,
    MONGODB_ERROR_INTERVAL,
)
from prozorro.risks.models import PaginatedList
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
            ("risks.worked.id", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
    )
    edrpou_compound_with_date_index = IndexModel(
        [
            ("procuringEntityEDRPOU", ASCENDING),
            ("risks.worked.id", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
    )
    edrpou_compound_with_value_index = IndexModel(
        [
            ("procuringEntityEDRPOU", ASCENDING),
            ("risks.worked.id", ASCENDING),
            ("value.amount", ASCENDING),
        ],
        background=True,
    )
    date_assessed_index = IndexModel([("dateAssessed", ASCENDING)], background=True)
    risks_worked_index = IndexModel(
        [
            ("risks.worked.id", ASCENDING),
            ("value.amount", ASCENDING),
        ],
        background=True,
    )

    try:
        await get_risks_collection().create_indexes(
            [
                region_compound_index,
                edrpou_compound_with_date_index,
                edrpou_compound_with_value_index,
                date_assessed_index,
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
    if regions_list := kwargs.get("region"):
        filters["procuringEntityRegion"] = {"$in": [region.lower() for region in regions_list]}
    if edrpou := kwargs.get("edrpou"):
        filters["procuringEntityEDRPOU"] = edrpou
    if risks_list := kwargs.get("risks"):
        filters["risks.worked"] = {"$elemMatch": {"id": {"$in": risks_list}}}
    return filters


async def find_tenders(skip=0, limit=20, **kwargs):
    collection = get_risks_collection()
    limit = min(limit, MAX_LIST_LIMIT)
    filters = _build_tender_filters(**kwargs)
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
        },
    )
    return result


def join_old_risks_with_new_ones(risks, tender):
    new_worked_risks = [risk["id"] for risk in risks["worked"]]
    new_other_risks = [risk["id"] for risk in risks["other"]]
    for worked_risk in tender.get("risks", {}).get("worked", []):
        if worked_risk["id"] not in new_worked_risks:
            risks["worked"].append(worked_risk)
    for other_risk in tender.get("risks", {}).get("other", []):
        if other_risk["id"] not in new_other_risks:
            risks["other"].append(other_risk)
    return risks


async def update_tender_risks(uid, risks, additional_fields):
    filters = {"_id": uid}
    while True:
        tender = await get_risks_collection().find_one({"_id": uid})
        if tender:
            risks = join_old_risks_with_new_ones(risks, tender)
            filters["dateAssessed"] = tender.get("dateAssessed")
        try:
            result = await get_risks_collection().find_one_and_update(
                filters,
                {
                    "$set": {
                        "_id": uid,
                        "risks": risks,
                        **additional_fields,
                    }
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
    limit = min(limit, MAX_LIST_LIMIT)
    count = await collection.count_documents(filters)
    try:
        cursor = collection.find(filters, projection=projection, max_time_ms=MAX_TIME_QUERY).skip(skip).limit(limit)
    except ExecutionTimeout as exc:
        logger.error(f"Filter tenders {type(exc)}: {exc}, filters: {filters}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        raise web.HTTPRequestTimeout(text="Please change filters combination to optimize query (e.g. edrpou + risks)")
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


async def get_tender(tender_id):
    collection = get_tenders_collection()
    try:
        result = await collection.find_one({"_id": tender_id})
    except PyMongoError as e:
        logger.error(f"Get tender {type(e)}: {e}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        return None
    return result
