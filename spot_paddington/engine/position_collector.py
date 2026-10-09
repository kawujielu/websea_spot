import asyncio
import time

from core_internal.abc_asset import abc_asset_position_instance
from core_external.external_asset import external_asset_position_instance
from core_external.deposit_withdraw_fee import deposit_withdraw_positions_instance
from many_configs import global_variable
from scaffold.mysql import Hedge_MysqlSession
import pandas as pd


async def abc_position_collector():
    await abc_asset_position_instance.run()


async def deposit_withdraw_position_collector():
    await deposit_withdraw_positions_instance.run()

# async def external_position_collector():
#     await external_asset_position_instance.run()

# TODO hyy 这个没有用？
# async def some_function():
#     """
#         todo @hyy
#         扫描成交和订单信息监控数据库里档数据
#         外部：每个order记录更新此order之后档对冲缺口
#         内部：加一个表每次插入供以后排查问题使用，另一个表只更新供对冲使用
#         对冲名字不一样的特殊处理
#         todo @andres
#         min(总量/get_best_ask_bid, 单次出口，钱包资金)
#
#         # 之后再搞
#         异常情况下撤单 查询订单等处理
#     """
#     # 定时任务，trades表获取n小时的之前的表
#     h = 24
#     now_time = time.time()
#     end_time = int(now_time - 60 * 60 * 1)
#     start_time = int(end_time - 60 * 60 * h)
#
#     start_time_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
#     end_time_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
#
#     sql = f"select * from trades where create_time between '{start_time_dt}' and '{end_time_dt}'"
#
#     res = await Hedge_MysqlSession.fetch_all(sql)
#     title = ['tradeId', 'orderId', 'exchange', 'time', 'symbol', 'side', 'price', 'amount', 'fee', 'feecoin',
#              'create_time', 'update_time', 'base_amount', 'quote_amount', 'fee_amount']
#
#     df = pd.DataFrame(columns=title, data=res)
#     df['tradeId'] = df['tradeId'].astype(str)
#     mess = ""
#     for symbol, exchange in dict(zip(df['symbol'], df['exchange'])).items():
#         df1 = df[(df['exchange'] == exchange) & (df['symbol'] == symbol)]
#         res = await global_variable.EXTERNAL_EXCHANGE_INSTANCES[exchange].get_trades_history(symbol,
#                                                                                              startTime=start_time * 1000,
#                                                                                              endTime=end_time * 1000)
#         if res:
#             df_trades = pd.DataFrame(res)
#             dff = pd.merge(df1, df_trades, on='tradeId', how='left')
#             dff['orderId_xy'] = (dff['orderId_x'] == dff['orderId_y'])
#             dff['amount_xy'] = (dff['amount_x'] - dff['amount_x'])
#             dff['price_xy'] = (dff['price_x'] - dff['price_y'])
#
#             dff = dff[(dff.orderId_xy == False) | (dff.amount_xy != 0) | (dff.price_xy != 0)]
#             if not dff.empty:
#                 tradeId = dff['tradeId'].unique()
#                 mess += f'{exchange}:{symbol}:tradeId:{tradeId}\n'
#     if mess:
#         print('订单异常', mess)
#     await asyncio.sleep(h * 60 * 60)
#
#
# if __name__ == '__main__':
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     while True:
#         loop.run_until_complete(some_function())
