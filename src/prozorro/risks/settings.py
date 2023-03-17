from pymongo import ReadPreference
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from zoneinfo import ZoneInfo
import sys
import os

API_HOST = os.environ.get("PUBLIC_API_HOST", "https://api.prozorro.gov.ua")
API_VERSION = os.environ.get("API_VERSION", "2.5")
BASE_URL = f"{API_HOST}/api/{API_VERSION}/tenders"

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://mongo:27017/")
DB_NAME = os.environ.get("DB_NAME", "prozorro-risks")
# 'PRIMARY', 'PRIMARY_PREFERRED', 'SECONDARY', 'SECONDARY_PREFERRED', 'NEAREST',
READ_PREFERENCE = getattr(ReadPreference, os.environ.get("READ_PREFERENCE", "PRIMARY"))
raw_write_concert = os.environ.get("WRITE_CONCERN", "1")
WRITE_CONCERN = WriteConcern(
    w=int(raw_write_concert) if raw_write_concert.isnumeric() else raw_write_concert
)
READ_CONCERN = ReadConcern(level=os.environ.get("READ_CONCERN") or None)

SWAGGER_DOC_AVAILABLE = bool(os.environ.get("SWAGGER_DOC_AVAILABLE", True))

IS_TEST = "test" in sys.argv[0]
SENTRY_DSN = os.getenv("SENTRY_DSN")
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Kiev"))
CLIENT_MAX_SIZE = int(os.getenv("CLIENT_MAX_SIZE", 1024**2 * 100))

MAX_LIST_LIMIT = int(os.environ.get("MAX_LIST_LIMIT", 1000))
