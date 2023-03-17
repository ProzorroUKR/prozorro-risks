from aiohttp.web import json_response as base_json_response
from datetime import datetime, timezone
from bson import ObjectId
from uuid import UUID
import json


def to_iso_format(obj):
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=timezone.utc).astimezone(tz=timezone.utc)
    return obj.isoformat()


def json_serialize(obj):
    if isinstance(obj, datetime):
        return to_iso_format(obj)
    if isinstance(obj, ObjectId) or isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, set):
        return list(sorted(obj))
    raise TypeError(f"Type {type(obj)} not serializable")


def json_dumps(*args, **kwargs):
    kwargs["default"] = json_serialize
    return json.dumps(*args, **kwargs)


def json_response(*args, **kwargs):
    return base_json_response(dumps=json_dumps, *args, **kwargs)
