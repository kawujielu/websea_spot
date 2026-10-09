'''
    查询现货刷量账户成交明细
'''

import asyncio
from abcapi_plus import AbcApi

token = '0fed027e443de5db584f8b9712681162'
secret = 'fwl5sp7ayb1fc9uxvjdi'
task = AbcApi(token=token, secret_key=secret, )


async def main():
    res = await task.trades(symbol="JTO_USDT", size=1000)
    print(res)



if __name__ == "__main__":
    asyncio.run(main())

