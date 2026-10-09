import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exchanges.restful_api.abc_spot import AApi
from libs import libs_account
import asyncio

accounts = libs_account.account


async def add_order_big(symbol, price, amount):
    print(f'{symbol=}, {price=}, {amount=}')
    websea = AApi(token=accounts['maker_near']['token'], secret_key=accounts['maker_near']['sk'])
    sell_order = websea.add_asyncio(symbol=symbol, type='sell-limit', price=float(price) * 1.1, amount=amount)
    print('sell order', sell_order)
    buy_order = websea.add_asyncio(symbol=symbol, type='buy-limit', price=float(price) * 0.9, amount=amount)
    print('buy order', buy_order)


async def main():
    import sys
    symbol = sys.argv[1]
    price = sys.argv[2]
    amount = sys.argv[3]
    await add_order_big(symbol=symbol, price=price, amount=amount)


if __name__ == '__main__':
    asyncio.run(main())
