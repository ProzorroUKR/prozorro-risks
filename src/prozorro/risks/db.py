import asyncio
import logging
import re
from contextvars import ContextVar
from distutils.util import strtobool

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
    SAS_24_RULES_FROM,
)
from prozorro.risks.models import RiskIndicatorEnum
from prozorro.risks.utils import tender_created_after_release
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
    """
    Create plain and compound indexes for risks collection
    """
    region_compound_index = IndexModel(
        [
            ("procuringEntityRegion", ASCENDING),
            ("worked_risks", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    edrpou_compound_with_date_index = IndexModel(
        [
            ("procuringEntityEDRPOU", ASCENDING),
            ("worked_risks", ASCENDING),
            ("dateAssessed", ASCENDING),
        ],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    date_assessed_risked_index = IndexModel(
        [("dateAssessed", ASCENDING)],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    value_amount_index = IndexModel(
        [("value.amount", ASCENDING)],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    risks_worked_index = IndexModel(
        [
            ("worked_risks", ASCENDING),
            ("value.amount", ASCENDING),
        ],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    terminated_index = IndexModel(
        [("terminated", ASCENDING)],
        background=True,
        partialFilterExpression={
            "has_risks": True,
        },
    )
    # for risks feed
    date_assessed_feed_index = IndexModel(
        [("dateAssessed", DESCENDING)],
        background=True,
    )

    try:
        await get_risks_collection().create_indexes(
            [
                region_compound_index,
                edrpou_compound_with_date_index,
                date_assessed_risked_index,
                value_amount_index,
                risks_worked_index,
                terminated_index,
                date_assessed_feed_index,
            ]
        )
    except PyMongoError as e:
        logger.exception(e)


async def init_tender_indexes():
    """
    Create indexes for tenders collection
    """
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
    """
    Get risks for provided tender id
    :param tender_id: str Id of tender
    :return: dict Tender with assessed risks result
    :raise: HTTPInternalServerError during mongo error
    :raise: HTTPNotFound if there is no tender in database with provided tender_id
    """
    collection = get_risks_collection()
    try:
        result = await collection.find_one(
            {"_id": tender_id},
            projection={
                "procuringEntityRegion": False,
                "procuringEntityEDRPOU": False,
                "worked_risks": False,
                "contracts": False,
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
    """
    Build filters for tenders query
    :return: dict Dict of ready filters
    """
    filters = {}
    worked_risks_filter = []
    contains_all_risks = False
    if tender_id := kwargs.get("tender_id"):
        filters["_id"] = tender_id
    filters["has_risks"] = True
    if regions_list := kwargs.get("region"):
        filters["procuringEntityRegion"] = {"$in": regions_list}
    if edrpou := kwargs.get("edrpou"):
        filters["procuringEntityEDRPOU"] = edrpou
    if owners_list := kwargs.get("owner"):
        worked_risks_filter = [re.compile(f"^{owner}") for owner in owners_list]
    # if there are filters by owner and by risks, then we are looking only at risks filter
    if risks_list := kwargs.get("risks"):
        worked_risks_filter = risks_list
    if risks_all := kwargs.get("risks_all"):
        try:
            contains_all_risks = bool(strtobool(risks_all))
        except ValueError:
            contains_all_risks = False
    if worked_risks_filter:
        filters["worked_risks"] = {"$all": worked_risks_filter} if contains_all_risks else {"$in": worked_risks_filter}
    if terminated := kwargs.get("terminated"):
        try:
            filters["terminated"] = bool(strtobool(terminated))
        except ValueError:
            pass
    return filters


async def find_tenders(skip=0, limit=20, **kwargs):
    """
    Get list of tenders, filtered by request params
    :param skip: int Number of documents to skip (needed for pagination)
    :param limit: int Number of documents per page (needed for pagination)
    :return: dict with filtered items and total count
    """
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
            "contracts": False,
        },
    )
    return result


async def get_tenders_risks_feed(fields, offset_value=None, descending=False, limit=20):
    collection = get_risks_collection()
    filters = dict()
    if offset_value:
        filters["dateAssessed"] = {"$lt" if descending else "$gt": offset_value}
    cursor = collection.find(
        filter=filters,
        projection={field_name: 1 for field_name in fields},
        limit=limit,
        sort=(("dateAssessed", DESCENDING if descending else ASCENDING),),
    )
    items = await cursor.to_list(length=None)
    return items


def join_old_risks_with_new_ones(risks, tender):
    """
    Join previous results of tender risks assessment, create log and add it to risk's history.
    :param risks: dict New assessed risks result {"sas-3-1": [...], "sas-3-2": [...]}
    :param tender: dict Tender object from risks database with previously assessed risks indicators
    :return: tuple Concatenated object of old and new risks for tender and array of total worked risk's identifiers
    """
    tender_risks = tender.get("risks", {})
    tender_worked_risks = set(tender.get("worked_risks", []))
    for risk_id, risk_items in risks.items():
        current_risk_items = {}
        for previous_risk_item in tender_risks.get(risk_id, []):
            item_key = "tender" if "item" not in previous_risk_item else previous_risk_item["item"]["id"]
            current_risk_items[item_key] = previous_risk_item
        for risk_data in risk_items:
            if risk_data["indicator"] == RiskIndicatorEnum.use_previous_result:
                continue
            log = {"date": risk_data["date"], "indicator": risk_data["indicator"]}
            item_key = "tender" if "item" not in risk_data else risk_data["item"]["id"]
            history = current_risk_items.get(item_key, {}).get("history", [])
            history.append(log)
            risk_data["history"] = history
            current_risk_items[item_key] = risk_data
        if risk_results := list(current_risk_items.values()):
            tender_risks[risk_id] = risk_results
            worked_items = [item for item in risk_results if item["indicator"] == RiskIndicatorEnum.risk_found]
            if worked_items:
                tender_worked_risks.add(risk_id)
            elif risk_id in tender_worked_risks:
                tender_worked_risks.remove(risk_id)
    return tender_risks, list(tender_worked_risks)


def update_contracts_statuses(contracts, tender):
    tender_contracts = tender.get("contracts", {})
    for contract in contracts:
        tender_contracts[contract["id"]] = contract.get("status")
    return tender_contracts


def tender_is_terminated(tender, contracts, new_status):
    contract_statuses = set(contracts.values())
    status = new_status or tender.get("status")
    return (
        status in ("unsuccessful", "cancelled")
        or (
            status == "complete"
            and len(contract_statuses) > 0
            and not contract_statuses.intersection({"active", "pending"})
        )
    )


async def update_tender_risks(uid, risks, additional_fields, contracts=None):
    filters = {"_id": uid}
    while True:
        try:
            tender = await get_risks_collection().find_one({"_id": uid})
            updated_contracts = update_contracts_statuses(contracts, tender if tender else {}) if contracts else {}
            set_data = {
                "_id": uid,
                "contracts": updated_contracts,
                **additional_fields,
            }
            if risks:
                risks, worked_risks = join_old_risks_with_new_ones(risks, tender if tender else {})
                set_data.update({
                    "risks": risks,
                    "worked_risks": worked_risks,
                    "has_risks": len(worked_risks) > 0,
                })
            if tender_created_after_release(tender if tender else additional_fields, SAS_24_RULES_FROM):
                set_data["terminated"] = tender_is_terminated(
                    tender if tender else {},
                    updated_contracts,
                    new_status=additional_fields.get("status")
                )
            if tender:
                filters["dateAssessed"] = tender.get("dateAssessed")
            result = await get_risks_collection().find_one_and_update(
                filters,
                {"$set": set_data},
                upsert=True,
                session=session_var.get(),
            )
        except PyMongoError as e:
            logger.warning(
                f"Update risks warning {type(e)}: {e}. Update will be repeated",
                extra={"MESSAGE_ID": "MONGODB_EXC"}
            )
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
        cursor = collection.find(filters, projection=projection, max_time_ms=MAX_TIME_QUERY).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        items = await cursor.to_list(length=None)
        # should be added additional field for using index during counting documents
        filters.update({"dateAssessed": {"$gte": "2023-01-01T00:00:00+02:00"}})
        count = await collection.count_documents(filters, maxTimeMS=MAX_TIME_QUERY)
    except ExecutionTimeout as exc:
        logger.error(f"Filter tenders {type(exc)}: {exc}, filters: {filters}", extra={"MESSAGE_ID": "MONGODB_EXC"})
        raise web.HTTPRequestTimeout(text="Please change filters combination to optimize query (e.g. edrpou + risks)")
    return dict(items=items, count=count)


async def get_distinct_values(field):
    return await get_risks_collection().distinct(field, {"has_risks": True, field: {"$nin": ["", None]}})


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
