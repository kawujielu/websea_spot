import asyncio
from abcapi_plus import AbcApi
from libs import libs_account
symbol = "USDQ-USDT"
market_price = 1

open_price = market_price / (1+1)
hight_price = market_price * 1.2

amount = 15/market_price

spec_instance = AbcApi(token=libs_account["spot_bak_4"]["token"], secret_key=libs_account["spot_bak_4"]["sk"], )


async def add1():
    res = await spec_instance.add(symbol, "sell-limit", amount, open_price, )
    print(res)

import random
async def add2():

    big_order = random.uniform(5, 5*2)
    res = await spec_instance.add(symbol, "sell-limit", big_order, 1.01 , )
    return
    for i in range(11, 15):
        res = await spec_instance.add(symbol, "sell-limit", big_order, 1.5 + i * 0.01 , )
    
    big_order = random.uniform(50, 80)
    for i in range(15, 20):
        res = await spec_instance.add(symbol, "buy-limit", big_order, 0.1 + i * 0.01, )
        print(res)


if __name__ == "__main__":
    #asyncio.run(add1())
    asyncio.run(add2())


