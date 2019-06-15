import json
import logging
import os
import ssl

import requests
from aiohttp import ClientSession, web


log = logging.getLogger(__name__)


async def handle(request):
    try:
        params = {
            "code": request.query.get("code"),
            "client_id": os.getenv("CLIENT_ID"),
            "client_secret": os.getenv("CLIENT_SECRET"),
            "redirect_uri": os.getenv("REDIRECT_URI"),
        }

        data = requests.get(
            url="https://slack.com/api/oauth.access", params=params
        ).json()

        if data["ok"]:
            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": data["error"]})

    except Exception as exc:
        log.info(exc)


async def handle_root(request):
    return web.json_response({"message": "ok"})


app = web.Application()
app.add_routes([web.get("/", handle_root), web.get("/auth/redirect", handle)])

web.run_app(app)
