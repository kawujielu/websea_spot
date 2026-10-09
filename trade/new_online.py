import random
import asyncio
import aiohttp
from abcapi_plus import AbcApi
from libs import libs_account

step_percent = 0.08

# symbol -> market_price
symbols = {
    "SKHYON-USDT": 165,
}

spec_instance = AbcApi(token=libs_account["spot_bak_4"]["token"], secret_key=libs_account["spot_bak_4"]["sk"], )


async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.text()


async def open_status(symbol):
    #### 测试
    # risk_host = "https://riskapi.wbspre.net"
    # token = "d5ee2eedfcf7adc285db4967bd86910d"
    #### 线上
    risk_host = "https://riskapi.websea.work"
    token = "c1cf4185b2bed317aeb6e6674491fbef"
    url = f'{risk_host}/api/open/get?url=symbol/setstatus&token={token}&symbol={symbol}&open_status=1'
    async with aiohttp.ClientSession() as session:
        res = await fetch_url(session, url)
        print(f"open_status {symbol} {res=}")


async def process_symbol(symbol, market_price):
    open_price = market_price / (1 + 0.2)
    high_price = market_price * (1 + min(0.05, step_percent))
    amount = 15 / market_price

    cancel_res = await spec_instance.cancel(symbol=symbol)
    print(f"{symbol} {cancel_res=}")

    for i in range(10):
        cur_price = open_price * (1 + step_percent)**i
        cur_amount = random.uniform(amount, amount * 3)
        if cur_price > high_price:
            cur_price = high_price
            res1 = await spec_instance.add(symbol, "sell-limit", cur_amount, cur_price, )
            res2 = await spec_instance.add(symbol, "buy-limit", cur_amount, cur_price, )
            print(f"{symbol} {cur_price=} {cur_amount=} {res1} {res2}")
            break
        # 撮合开盘价
        res1 = await spec_instance.add(symbol, "sell-limit", cur_amount, cur_price, )
        res2 = await spec_instance.add(symbol, "buy-limit", cur_amount, cur_price, )
        print(f"{symbol} {cur_price=} {cur_amount=} {res1} {res2}")

    # 正常价格成交
    res1 = await spec_instance.add(symbol, "sell-limit", amount, market_price, )
    res2 = await spec_instance.add(symbol, "buy-limit", amount, market_price, )
    print(f"{symbol} {market_price=} {amount=} {res1} {res2}")

    big_order = 2000 / market_price
    res1 = await spec_instance.add(symbol, "sell-limit", big_order, market_price * 1.3, )
    res2 = await spec_instance.add(symbol, "buy-limit", big_order, market_price * 0.7, )
    print(f"{symbol} {market_price * 1.3=} {market_price * 0.7=} {big_order=} {res1} {res2}")

    await open_status(symbol)


async def main():
    await asyncio.gather(*(process_symbol(s, p) for s, p in symbols.items()))


if __name__ == "__main__":
    asyncio.run(main())

