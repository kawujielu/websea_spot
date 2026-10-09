from scaffold.aiohttp import G_RequestSession
import asyncio
import traceback
from loguru import logger


headers = {
    'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}


class BinanceApi:
    async def funding_rate(self):
        bn_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        async with G_RequestSession.request.get(bn_url, headers=headers) as r:
            res = await r.text()
            logger.info(res)


async def funding_rate_main():
    exchanges = [BinanceApi()]
    try:

        tasks = [asyncio.create_task(ex.funding_rate()) for ex in exchanges]

        await asyncio.wait(tasks)
    except:
        logger.error(f"funding_rate_main {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(funding_rate_main())
