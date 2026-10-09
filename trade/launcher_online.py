import asyncio
from abcapi_plus import AbcApi
from libs import libs_account
symbol = "XAUT-USDT"
market_price = 3992.3

open_price = market_price / (1+0.1)
hight_price = market_price * 1.05

amount = 15/market_price

spec_instance = AbcApi(token=libs_account["spot_bak_4"]["token"], secret_key=libs_account["spot_bak_4"]["sk"], )


async def add1():
    pp = 3992.3
    res = await spec_instance.add(symbol, "sell-limit", amount, pp, )
    res = await spec_instance.add(symbol, "buy-limit", amount, pp, )
    print(res)


async def add2():
    # 撮合开盘价
    res = await spec_instance.add(symbol, "sell-limit", amount, open_price, )
    print(res)
    res = await spec_instance.add(symbol, "buy-limit", amount, open_price, )
    print(res)
    
    # hight price 
    res = await spec_instance.add(symbol, "sell-limit", amount, hight_price, )
    print(res)
    res = await spec_instance.add(symbol, "buy-limit", amount, hight_price, )
    print(res)
    
    # 正常价格成交
    res = await spec_instance.add(symbol, "sell-limit", amount, market_price, )
    print(res)
    res = await spec_instance.add(symbol, "buy-limit", amount, market_price, )
    print(res)

    big_order = 2000 / market_price
    res = await spec_instance.add(symbol, "sell-limit", big_order, market_price * 1.3, )
    print(res)
    res = await spec_instance.add(symbol, "buy-limit", big_order, market_price * 0.7, )
    print(res)


if __name__ == "__main__":
    asyncio.run(add1())
    #asyncio.run(add2())


