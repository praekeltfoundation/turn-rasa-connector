import time

import pytest

from .fake_turn import app


@pytest.mark.asyncio
async def test_create_message():
    start = time.time()
    request, response = await app.asgi_client.post("/v1/messages")
    assert time.time() - start > 0.05
    assert response.status == 201
    assert response.json()["messages"][0]["id"]


@pytest.mark.asyncio
async def test_create_media():
    start = time.time()
    request, response = await app.asgi_client.post("/v1/media")
    assert time.time() - start > 0.05
    assert response.status == 201
    assert response.json()["media"][0]["id"]


@pytest.mark.asyncio
async def test_rerun_automation():
    start = time.time()
    request, response = await app.asgi_client.post(
        "/v1/messages/test-message-id/automation"
    )
    assert time.time() - start > 0.05
    assert response.status == 201
    assert response.json() == {}
