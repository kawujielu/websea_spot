import os, sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import json
import time
from libs.send_tglegram_msg import send_telegram_async
from libs import libs_price_async
from scaffold.mysql import Hedge_MysqlSession
from libs import heartbeat

price_redis_db = libs_price_async.redis_db_market_price
config_redis_db = libs_price_async.redis_db_control

'''
    pools_dict = {'BTC': {'amounts': -0.0001763570522883292,
                 'amounts_as_AQ': -39.520994640990516,
                 'avg_AQ_price': 108675.28403878243,
                 'consequent_hedging_hours': 0.0,
                 'hedged_currencies': 'BTC',
                 'hedging_states': 0,
                 'is_alertings': 0,
                 'thresholds': -0.8924727420975108,
                 'thresholds_as_AQ': -200000.0}}
'''


async def get_hedge_datas():
    abc_asset_gap = await Hedge_MysqlSession.fetch_all(f'''select coin, amount from abc_asset_gap''')
    external_asset_gap = await Hedge_MysqlSession.fetch_all(f'''select coin,amount from external_asset_gap''')
    abc_asset_map = {info[0]: float(info[1]) for info in abc_asset_gap if info[0] and info[1]}
    external_asset_map = {info[0]: float(info[1]) for info in external_asset_gap if info[0] and info[1]}
    hedge_config = await Hedge_MysqlSession.fetch_all('select currency,config from hedge_config')
    hedge_config_map = {info[0]: json.loads(info[1])['hedge_threshold_USDT'] for info in hedge_config}
    currency_list = list(abc_asset_map.keys()) + list(external_asset_map.keys())
    currency_list = set(currency_list)
    asset_map = {}
    for currency in currency_list:
        asset_map[currency] = abc_asset_map.get(currency, 0) + external_asset_map.get(currency, 0)
    pools_dict = {}
    for currency, amount in asset_map.items():
        amount = amount
        threshold_usdt = hedge_config_map.get(currency, 0)
        price = list((await price_redis_db.async_connection.hgetall(currency + '-USDT')).values())
        avg_cny_price = float(price[0]) * 7 if price else 0
        pools_dict.update(
            {currency: {'amount': amount, 'threshold_usdt': threshold_usdt, 'avg_cny_price': avg_cny_price}})
    # 同步盒子层
    hedge_dict = {}
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    for coin, value in pools_dict.items():
        hedge_dict[coin] = {}
    for coin, value in pools_dict.items():
        hedge_dict[coin]["amounts"] = value['amount']
        hedge_dict[coin]["thresholds"] = str(value['threshold_usdt']) + 'USDT'
        hedge_dict[coin]["hedged_currencies"] = coin
        hedge_dict[coin]["amounts_as_AQ"] = value['amount'] * value['avg_cny_price']
        hedge_dict[coin]["time"] = cu_time
        try:
            threshold_value = float(value['threshold_usdt']) * 7
            hedge_dict[coin]["thresholds_as_AQ"] = threshold_value
        except:
            continue
            await send_telegram_async(message=f'{cu_time}| hedge_redis【{coin}】thresholds {value[1]}无法转换为CNY')
    return hedge_dict


async def store_pools_history_to_redis():
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    name = 'update_price_percent_via_hedge'
    hedge_datas = await get_hedge_datas()
    msg = ''
    for k, v in hedge_datas.items():
        try:
            await config_redis_db.async_connection.hset(name, k, json.dumps(v))
        except Exception as error:
            print(f"{k} {error}\n{traceback.format_exc()}")
            msg = f'{traceback.format_exc()}'
    if msg:
        await send_telegram_async(message=f'hedge_redis update failed\n{msg}', ser='warning')
    print(f'{cu_time} ==> 更新结束' + '=' * 100)
    await heartbeat.i_live_well("现货对冲缺口干预现货流动性", 15, 66)


async def main():
    while True:
        await store_pools_history_to_redis()
        await asyncio.sleep(2)


if __name__ == '__main__':
    asyncio.run(main())
