import asyncio
from loguru import logger
import traceback


async def ws_ping(ws, msg, sleep_time):
    while True:
        try:
            await ws.send(msg)
            await asyncio.sleep(sleep_time)
        except asyncio.exceptions.CancelledError:
            break
        except:
            logger.error(f"{traceback.format_exc()}")
            await asyncio.sleep(2)


def ping_enhance(self, data="ping"):
    ref_ping = self.ping

    async def ping_enhance_fun():
        # logger.info("ping_enhance-----------")
        await self.send(data)
        return await ref_ping()
    return ping_enhance_fun


def ping_pong_enhance(self, data="ping"):
    ref_ping = self.ping

    async def ping_enhance_fun():
        # logger.info("ping_enhance-----------")
        await self.pong()
        return await ref_ping()
    return ping_enhance_fun
