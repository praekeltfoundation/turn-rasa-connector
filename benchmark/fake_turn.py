import asyncio
import random
from uuid import uuid4

from sanic import Sanic
from sanic.response import json

app = Sanic("fake_turn")

MINIMUM_LATENCY = 0.05
MAXIMUM_LATENCY = 0.5


@app.post("/v1/messages")
async def create_message(request):
    await asyncio.sleep(random.uniform(MINIMUM_LATENCY, MAXIMUM_LATENCY))
    return json({"messages": [{"id": uuid4().hex}]}, status=201)


@app.post("/v1/media")
async def create_media(request):
    await asyncio.sleep(random.uniform(MINIMUM_LATENCY, MAXIMUM_LATENCY))
    return json({"media": [{"id": uuid4().hex}]}, status=201)


@app.post("v1/messages/<message_id>/automation")
async def rerun_automation(request, message_id):
    await asyncio.sleep(random.uniform(MINIMUM_LATENCY, MAXIMUM_LATENCY))
    return json({}, status=201)


if __name__ == "__main__":
    app.run(port=8080)
