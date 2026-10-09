import asyncio
from abcapi_plus import AbcApi
from libs import libs_account

spec_instance = AbcApi(token=libs_account["spot_bak_4"]["token"], secret_key=libs_account["spot_bak_4"]["sk"], )


async def add2():
    symbol1 = "EURR-USDT"
    # 撮合开盘价
    res = await spec_instance.add(symbol1, "sell-limit", 20, 1.132, )
    print(res)
    res = await spec_instance.add(symbol1, "buy-limit", 20, 1.132, )
    print(res)
    symbol2 = "EURQ-USDT"
    # hight price 
    res = await spec_instance.add(symbol2, "sell-limit", 15, 1.13, )
    print(res)
    res = await spec_instance.add(symbol2, "buy-limit", 15, 1.13, )
    print(res)
    

if __name__ == "__main__":
    asyncio.run(add2())


