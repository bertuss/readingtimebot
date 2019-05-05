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
            "redirect_uri": os.getenv("REDIRECT_URI")
        }

        log.warning(params)

        data = requests.get(url="https://slack.com/api/oauth.access", params=params).json() 

        log.warning(data)

        if data["ok"]:
            # {
            #     "user_id": "",
            #     "ok": true,
            #     "team_name": "",
            #     "scope": "identify,bot",
            #     "team_id": "",
            #     "bot": {
            #         "bot_user_id": "",
            #         "bot_access_token": "."
            #     },
            #     "access_token": "."
            # }

            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": data["error"]})

    except Exception as exc:
        print(exc)


async def handle_root(request):
    return web.json_response({"message": "ok"})


app = web.Application()
app.add_routes([
    web.get('/', handle_root),
    web.get('/auth/redirect', handle),
])

ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain(
    os.getenv("CERT_FILE"),
    os.getenv("KEY_FILE")
)

web.run_app(app, ssl_context=ssl_context)
