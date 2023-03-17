from prozorro.risks.api import create_application
from prozorro.risks.db import flush_database, init_mongodb, get_database
from json import loads
import os.path
import pytest


def get_fixture_json(name):
    fixture_file = os.path.join("tests/fixtures", f"{name}.json")
    with open(fixture_file) as f:
        data = loads(f.read())
    return data


@pytest.fixture
async def db(event_loop):
    try:
        await init_mongodb()
        yield get_database()
    except Exception:
        await flush_database()


@pytest.fixture
async def api(event_loop, aiohttp_client):
    app = await aiohttp_client(create_application(on_cleanup=flush_database))
    app.get_fixture_json = get_fixture_json
    return app
