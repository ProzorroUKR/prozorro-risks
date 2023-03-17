async def test_ping(api):
    response = await api.get("/api/ping")
    assert response.status == 200
    assert "pong" == await response.text()


async def test_version(api):
    response = await api.get("/api/version")
    assert response.status == 200
    resp_json = await response.json()
    assert "api_version" in resp_json
