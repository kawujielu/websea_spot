import traceback

import time
from libs import libs_price_async, bsc_node_pools
import ujson
import numpy as np
import random
from many_configs import global_variable, spot_currency_config

SWAP_VOL_UPDATETIME = {}
SWAP_VOL = {}
VOLUM_COEFFICIENT_UPDATETIME = {}
VOLUM_COEFFICIENT = {}
config_update_time = {}


async def update_trade_volume_percent():
    try:
        update_time = config_update_time.get("TRADE_VOLUME_PERCENT_UPDATE", 0)
        time_now = time.time()
        if time_now - update_time > 60 * 1:
            config_update_time["TRADE_VOLUME_PERCENT_UPDATE"] = time_now

            redis_info = await libs_price_async.redis_db_control.async_connection.hgetall("trade_volume_percent")
            print("redis_info", redis_info)
            for r in redis_info:
                # 前端配置为币种，不能为交易对
                percent = min(max(0.0000001, float(redis_info[r])), 800.0)
                if r in global_variable.G_TRADE_CURRENCY_CONFIG:
                    global_variable.G_TRADE_CURRENCY_CONFIG[r]["market_value_percent"] = percent

    except BaseException as e:
        print("update_trade_volume_percent", repr(e))


async def update_contract_trade_volume_percent():
    try:
        update_time = config_update_time.get("CONTRACT_TRADE_VOLUME_PERCENT_UPDATE", 0)
        time_now = time.time()
        if time_now - update_time > 60 * 1:
            config_update_time["CONTRACT_TRADE_VOLUME_PERCENT_UPDATE"] = time_now
            redis_info = await libs_price_async.redis_db_control.async_connection.hgetall("contract_trade_volume_percent")
            print("contract_redis_info", redis_info)
            for r in redis_info:
                # 前端配置为币种，不能为交易对
                percent = min(max(0.0000001, float(redis_info[r])), 800.0)
                if r in global_variable.G_CONTRACT_TRADE_CURRENCY_CONFIG:
                    global_variable.G_CONTRACT_TRADE_CURRENCY_CONFIG[r]["market_value_percent"] = percent

    except BaseException as e:
        print("update_contract_trade_volume_percent", repr(e))


async def update_node():
    try:
        bsc_node_min = 8
        update_time = config_update_time.get("NODE_UPDATE", 0)
        time_now = time.time()
        if time_now - update_time > 60 * 5:
            config_update_time["NODE_UPDATE"] = time_now

            redis_info = await libs_price_async.redis_db_node.async_connection.hgetall("NODE_MONITOR")
            print("redis_info", redis_info)
            global_variable.BLOCK_NODE["BSC"] = []
            bsc_info = ujson.loads(redis_info["BSC"])
            if 'error' in bsc_info:
                bsc_info.pop('error')
            if 'timestamp' in bsc_info:
                bsc_info.pop('timestamp')
            for i in sorted(bsc_info):
                if len(global_variable.BLOCK_NODE["BSC"]) > bsc_node_min and int(i) > 10:   # BSC 3s出一块
                    break
                else:
                    global_variable.BLOCK_NODE["BSC"].extend(bsc_info[i])

            if len(global_variable.BLOCK_NODE["BSC"]) < bsc_node_min:
                global_variable.BLOCK_NODE["BSC"] = global_variable.BLOCK_NODE_LAST.get("BSC", bsc_node_pools)
    except BaseException as e:
        print("NODE_UPDATE", repr(e), traceback.format_exc())


async def get_swap_vol(symbol=None, name='swap_kline'):
    current_time = int(time.time())
    update_time = SWAP_VOL_UPDATETIME.get('update', 0)
    if current_time - update_time >= 60 * 1:
        swap_vol = await libs_price_async.redis_db_vol.async_connection.hgetall(name)
        for k, v in swap_vol.items():
            volume = ujson.loads(v)
            SWAP_VOL[k] = volume
        SWAP_VOL_UPDATETIME['update'] = current_time
        cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print('update_swap_vol', cu_time)
    if symbol:
        swap_vol = SWAP_VOL.get(symbol, {})
        vol_usdt = np.mean(swap_vol.get('volume_usdt', [0]))
        vol = np.mean(swap_vol.get('volume', [0]))
        results = {symbol: {'vol_usdt': round(vol_usdt, 2), 'vol': round(vol / random.uniform(10, 20), 8)}}
        # print('rs_get_swap_vol', results)
    else:
        results = {}
        swap_vol_dict = SWAP_VOL
        for symbol, value in swap_vol_dict.items():
            vol_usdt = np.mean(value.get('volume_usdt', [0]))
            vol = np.mean(value.get('volume', [0]))
            if vol:
                results[symbol] = {'vol_usdt': round(vol_usdt, 2), 'vol': round(vol / random.uniform(10, 20), 8)}
        # print('rs_get_swap_vol', results)
    return results


# TODO 逻辑验证
async def update_swap_vol():
    """
    如果外部拿到的数量小于10000U，就按照外部的数量来进行刷量
    大于10000U，按照当前刷量值乘以对应的倍数
    """
    try:
        # symbols_swap = ["MBOX-USDT", "SKILL-USDT", "DPET-USDT", "SPS-USDT", "BUNNY-USDT"]
        symbols_swap = []
        swap_vol = await get_swap_vol()
        print("swap_vol", swap_vol)
        for symbol in symbols_swap:
            vol_mul = None
            swap_symbol_usdt = swap_vol[symbol].get('vol_usdt', 0)
            if swap_symbol_usdt >= 3000000:
                vol_mul = 5
            elif swap_symbol_usdt >= 200000:
                vol_mul = 4
            elif swap_symbol_usdt >= 100000:
                vol_mul = 3
            elif swap_symbol_usdt >= 50000:
                vol_mul = 2
            elif swap_symbol_usdt >= 10000:
                vol_mul = 1
            currency = symbol.split("-")[0]
            if not global_variable.G_TRADE_CURRENCY_CONFIG[currency].get("self_market_value_org"):
                global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value_org"] = \
                    global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value"]
            if vol_mul:
                # print(symbol, vol_mul)
                global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value"] = \
                    global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value_org"] * (
                        1 + random.uniform(vol_mul - 0.5, vol_mul + 0.5)) * \
                    global_variable.G_TRADE_CURRENCY_CONFIG[currency].get("market_value_percent", 1)
            else:
                global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value"] = \
                    global_variable.G_TRADE_CURRENCY_CONFIG[currency]["self_market_value_org"] * \
                    global_variable.G_TRADE_CURRENCY_CONFIG[currency].get("market_value_percent", 1)
    except BaseException as e:
        print("update_swap_vol", repr(e))


async def update_symbol_precision():
    try:
        precision_dict = await libs_price_async.get_precision_config()
        if precision_dict:
            global_variable.SYMBOLS_ORDER_CONDITION.update(precision_dict)
    except BaseException as e:
        print("update_symbol_precision", repr(e))


async def get_vol_coefficient(name='24_volum_coefficient'):
    current_time = int(time.time())
    update_time = VOLUM_COEFFICIENT_UPDATETIME.get('update', 0)
    if current_time - update_time >= 60 * 10:
        VOLUM_COEFFICIENT_UPDATETIME['update'] = current_time
        volum_coefficient = await libs_price_async.redis_db_vol.async_connection.hgetall(name)
        for k, v in volum_coefficient.items():
            volume = ujson.loads(v)
            VOLUM_COEFFICIENT[k] = volume
        cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print('update_vol_coefficient', cu_time)
    vol_coefficient_dict = VOLUM_COEFFICIENT
    result = 1
    for key, value in vol_coefficient_dict.items():
        if key == 'mul' and value:
            result = value
    result = max(result, 0.5)
    result = min(result, 1.5)
    return result


async def update_vol_coefficient():
    try:
        vol_coefficient = await get_vol_coefficient()
        if vol_coefficient:
            spot_currency_config.TRADE_AREA_AVG_MAPPINGS.update(
                {
                 'USDT': spot_currency_config.TRADE_AREA_AVG_MAPPINGS_INI.get('USDT', 1/4) * vol_coefficient,
                 }
            )
        # print('刷量对标交易区的数量', spot_currency_config.TRADE_AREA_AVG_MAPPINGS)
    except BaseException as e:
        print("update_vol_coefficient", repr(e))


async def update_price_percent(symbol):
    update_time = global_variable.REDIS_PRICE_PERCENT.get("PRICE_PERCENT_UPDATE", 0)
    time_now = time.time()

    # redis和配置文件买卖一价差，未考虑特定值
    if time_now - update_time > 60 * 10:
        global_variable.REDIS_PRICE_PERCENT["PRICE_PERCENT_UPDATE"] = time_now
        redis_info = await libs_price_async.redis_db_control.async_connection.hgetall("price_percent")
        ask_bid_percent_temp = {}
        if "PRICE_PERCENT_INIT" not in global_variable.REDIS_PRICE_PERCENT:
            for currency, value in spot_currency_config.SPOT_CURRENCY_CONFIG.items():
                ask_bid_percent_temp.update(value.get("ask_bid_percent_spec", {}))
            global_variable.REDIS_PRICE_PERCENT["PRICE_PERCENT_INIT"] = True

        # 没有删除功能
        for r in redis_info:
            if r.endswith('_PRICE'):
                continue
            else:
                ask_bid_percent_temp[r] = min(max(0.0, float(redis_info[r])), 1)
        global_variable.REDIS_PRICE_PERCENT.update(ask_bid_percent_temp)

    # 买卖一价格计算最大价差
    update_time = global_variable.PRICE_PERCENT.get(f"{symbol}_UPDATE", 0)
    time_now = time.time()
    if time_now - update_time > 60 * 10:
        global_variable.PRICE_PERCENT[f"{symbol}_UPDATE"] = time_now
        ask1_init, bid1_init = await libs_price_async.get_weight_aks_bid(symbol)
        if ask1_init and bid1_init:
            percent = ((ask1_init - bid1_init) / bid1_init)
            global_variable.PRICE_PERCENT[f"{symbol}"] = percent
    return max(global_variable.PRICE_PERCENT.get(symbol, 0), global_variable.REDIS_PRICE_PERCENT.get(symbol, 0))