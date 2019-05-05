import asyncio
import json
import logging
import os
import random
import re
import sys

import aiohttp
import justext
import readtime
import requests
import slacker
import websockets
from aioslacker import Slacker


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)


URL_REGEX = re.compile(
    r"(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))",
    re.UNICODE,
)

RESPONSE_LIMIT_SECS = 100  # only respond if reading time is more than this

TLDR_LIMIT_SECS = 15 * 60

TLDR_RESPONSES = [
    "https://media.giphy.com/media/bWM2eWYfN3r20/giphy.gif",
    "https://media.giphy.com/media/10PcMWwtZSYk2k/giphy.gif",
    "https://media.giphy.com/media/kjelbEcB3I33a/giphy.gif",
    "https://media.giphy.com/media/AZemObXVMo4mY/giphy.gif",
    "https://media.giphy.com/media/paZm4ruZ4MDCg/giphy.gif",
    "https://media.giphy.com/media/NyjObFYNmwEM/giphy.gif",
    "https://media.giphy.com/media/11VgTdIuywPbSo/giphy-downsized-large.gif",
    "https://media.giphy.com/media/2d98nRiVVB6HS/giphy-downsized-large.gif",
    "https://media.giphy.com/media/1BFGiiHYS2dAbC0Lx1/giphy.gif",
    "https://media.giphy.com/media/z3eWAd2iZ9YQM/giphy.gif",
]


class Bot(object):
    def __init__(self, loop=None):
        self.slacker = Slacker(token=os.getenv("BOT_TOKEN", ""))
        self.websocket = None
        self.keepalive = None
        self.reconnecting = False
        self.listening = True
        self._message_id = 0

        if not loop:
            loop = asyncio.get_event_loop()

        self.loop = loop

    async def connect(self):
        log.info("Connecting to Slack")

        try:
            connection = await self.slacker.rtm.start()
            self.websocket = await websockets.connect(connection.body["url"])

            log.info("Connected successfully")

            if self.keepalive is None or self.keepalive.done():
                self.keepalive = self.loop.create_task(self.keepalive_websocket())

        except aiohttp.ClientOSError as error:
            log.error("Failed to connect to Slack, retrying in 10", error)
            await self.reconnect(10)
        except slacker.Error as error:
            log.error("Unable to connect to Slack due to {}".format(error))
        except Exception:
            await self.disconnect()
            raise

    async def reconnect(self, delay=None):
        try:
            self.reconnecting = True
            if delay is not None:
                await asyncio.sleep(delay)
            await self.connect()
        finally:
            self.reconnecting = False

    async def disconnect(self):
        await self.slacker.close()

    async def listen(self):
        while self.listening:
            try:
                await self.receive_from_websocket()
            except AttributeError:
                break

    async def receive_from_websocket(self):
        try:
            content = await self.websocket.recv()
            await self.process_message(json.loads(content))
        except websockets.exceptions.ConnectionClosed:
            log.info("Slack websocket closed, reconnecting...")
            await self.reconnect(5)

    async def process_message(self, message):
        if "type" in message and message["type"] == "message" and "user" in message:

            # Ignore bot messages
            if "subtype" in message and message["subtype"] == "bot_message":
                return

            urls = await self.get_urls(message["text"])

            if not urls:
                return

            for url in urls:
                rt_seconds, rt_text = await self.get_reading_time(url)
                if rt_text:
                    await self.slacker.chat.post_message(
                        message["channel"],
                        "Reading time: {}".format(rt_text),
                        as_user=True,
                    )
                if rt_seconds > TLDR_LIMIT_SECS:
                    await self.slacker.chat.post_message(
                        message["channel"], random.choice(TLDR_RESPONSES), as_user=True
                    )

    async def keepalive_websocket(self):
        while self.listening:
            await self.ping_websocket()

    async def ping_websocket(self):
        await asyncio.sleep(60)
        self._message_id += 1
        try:
            await self.websocket.send(
                json.dumps({"id": self._message_id, "type": "ping"})
            )
        except (
            websockets.exceptions.InvalidState,
            websockets.exceptions.ConnectionClosed,
            aiohttp.ClientOSError,
            TimeoutError,
        ):
            log.info("Slack websocket closed, reconnecting...")
            if not self.reconnecting:
                await self.reconnect()

    async def get_urls(self, text):
        return re.findall(URL_REGEX, text.lstrip("<").rstrip(">"))

    async def get_reading_time(self, url):
        try:
            html = requests.get(url).content
            paragraphs = justext.justext(html, justext.get_stoplist("English"))
            full_text = "\n\n".join(
                [p.text for p in paragraphs if not p.is_boilerplate]
            )
            result = readtime.of_text(full_text)

            if result.seconds <= RESPONSE_LIMIT_SECS:
                log.info("Article reading time under limit: {} secs, url=`{}`".format(
                    result.seconds,
                    url
                ))
                return 0, None

            return result.seconds, result.text
        except:
            pass


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        b = Bot(loop)
        loop.run_until_complete(b.connect())
        loop.run_until_complete(b.listen())

    except KeyboardInterrupt:
        log.info("Interrupted")

    finally:
        for task in asyncio.Task.all_tasks():
            task.cancel()
        loop.run_until_complete(b.disconnect())
        loop.close()
