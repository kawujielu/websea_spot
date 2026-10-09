from strategy.near_strategy import near_settings as ss1
import copy
import sys

from loguru import logger

from strategy.defense_strategy import defense_settings as ss2
from strategy.defense_strategy.defense_base import DefenseStrategyHub
from strategy.depth_strategy import depth_settings as ss3
from strategy.depth_strategy.depth_base import DepthStrategyHub
from strategy.near_strategy import near_settings as ss1
from strategy.near_strategy.near_base import NearStrategyHub


async def prepare_order(symbol, deal_choice):
    avg_plus = 1
    total = 0
    line=100*'-'
    mmld = NearStrategyHub(symbol=symbol, abc=abc, ss=ss1, logger=logger)
    bid_price, ask_price = await mmld.update_adj_price()
    buy_orders, sell_orders = mmld.prepare_orders(bid_price, ask_price)
    print(buy_orders)
    print(sell_orders)
    print(line+'NEAR'+line)
    sell_orders = [x[deal_choice] * avg_plus for x in sell_orders]
    buy_orders = [x[deal_choice] * avg_plus for x in buy_orders]
    total += sum(sell_orders)
    print("sell", sell_orders, '\n', "buy", buy_orders, '\n', sum(sell_orders))

    #
    mmld = DefenseStrategyHub(symbol=symbol, abc=abc, ss=ss2, logger=logger)
    bid_price, ask_price = await mmld.update_adj_price()
    buy_orders, sell_orders = mmld.prepare_orders(bid_price, ask_price)
    print(line+'DEFENSE'+line)

    sell_orders = [x[deal_choice] * avg_plus for x in sell_orders]
    buy_orders = [x[deal_choice] * avg_plus for x in buy_orders]
    total += sum(sell_orders)
    print("sell", sell_orders, '\n', "buy", buy_orders, '\n', sum(sell_orders))
    #

    #
    mmld = DepthStrategyHub(symbol=symbol, abc=abc, ss=ss3, logger=logger)
    # bid_price, ask_price = await mmld.update_adj_price()
    print(line+'DEPTH'+line)
    buy_orders, sell_orders = mmld.prepare_orders(bid_price, ask_price)
    sell_orders = [x[deal_choice] * avg_plus for x in sell_orders]
    buy_orders = [x[deal_choice] * avg_plus for x in buy_orders]
    total += sum(sell_orders)
    print("sell", sell_orders, '\n', "buy", buy_orders, '\n', sum(sell_orders))
    print(line+'end'+line)
    print('Total:',total)


if __name__ == '__main__':
    from config import accounts
    from abcapi_plus import AbcApi

    amount = "amount"
    price = "price"
    abc = AbcApi(**accounts[0])
    import asyncio

    # for symbols in symbols_USDT:
    asyncio.run(prepare_order("BTC-USDT", amount))
