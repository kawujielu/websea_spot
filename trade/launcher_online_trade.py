import asyncio
import random
from abcapi_plus import AbcApi
from libs import libs_account
symbol = "ASTER-USDT"
amount = 200 / 1

spec_instance = AbcApi(token=libs_account["spot_bak_4"]["token"], secret_key=libs_account["spot_bak_4"]["sk"], )


async def add1():
    for i in range(500):
        k = (1 / ((i+1)/60)) / 10
        amount_t = k * random.uniform(amount, amount*2)
        res = await spec_instance.spot_add_plus(symbol, amount_t)
        print(f"{amount_t=} {res=}")
        await asyncio.sleep(1)



if __name__ == "__main__":
    asyncio.run(add1())
