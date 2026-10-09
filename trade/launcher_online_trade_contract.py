import asyncio
import random
from abcapi_plus import AbcApi
from libs import libs_account
symbol1 = "KERNEL-USDT"
amount = 500

spec_instance = AbcApi(token=libs_account["contract_volume"]["token"], secret_key=libs_account["contract_volume"]["sk"], )


async def add1():
    for i in range(500):
        k = (1 / ((i+1)/60)) / 10
        amount_t = k * random.uniform(amount*0.5, amount*3)
        res = await spec_instance.contract_add_plus(symbol1, amount_t)
        print(f"{amount_t=} {res=}")
        await asyncio.sleep(1)



if __name__ == "__main__":
    asyncio.run(add1())

