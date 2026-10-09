import copy
import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import asyncio
# 导入中心化交易所对象
from exchanges.restful_api import binance, okex, huobi, gateio, mexc, bitget, kraken
from many_configs.global_variable import EXTERNAL_EXCHANGE_INSTANCES, EXCHANGE_GEARS, INTERVAL, trans_okex_symbols, \
    trans_bn_symbols, trans_gateio_symbols, trans_hb_symbols, trans_mexc_symbols, trans_bitget_symbols, trans_kraken_symbols
from many_configs import global_variable
import time
import ujson
import random
from many_configs.global_variable import WS_EXCHANGE_ACTIVE
from libs.recode_msg import recode_error_msg
from loguru import logger


async def best_ask_bid(symbol, exchange):
    # 返回市场最有档买卖一价格，ws数据如果有问题，restful获取 # todo hyy
    # G_SYMBOL_GEAR5
    # gear_data = {'asks': data["asks"], "bids": data["bids"], "ts": int(msg["time_ms"] / 1000)}
    #                             global_variable.SHARE_MEMORY_WS_INSTANCE['gateio'][symbol] = gear_data
    now_time = int(time.time())
    gear_data = global_variable.SHARE_MEMORY_WS_INSTANCE.get(exchange, {}).get(symbol, {})
    try:
        if abs(now_time - gear_data.get('ts', 0)) > 60:
            GEARS = EXCHANGE_GEARS[exchange]
            data = await EXTERNAL_EXCHANGE_INSTANCES[exchange].depth(symbol, limit=GEARS)
            logger.info(f'{symbol} | {exchange}| {data}')
            geardata = {'asks': data["asks"][0][0], "bids": data["bids"][0][0], "ts": now_time}
        else:
            geardata = {'asks': gear_data["asks"][0][0], "bids": gear_data["bids"][0][0], "ts": gear_data["ts"]}
    except Exception as error:
        # todo:  add_price = (float(price["asks"]) + float(price["bids"])) / 2
        # KeyError: 'asks'
        msg = f"{traceback.format_exc()}"
        await recode_error_msg(msg, server="spot_hedge")
        geardata = {}
    return geardata


async def update_ws_subscribe(symbols, exchange='bn', is_subscribe='subscribe'):
    # 配置变动后，更新交易对档订阅与取消
    '''
    :param symbols: []
    :param exchange: 'bn','okex','gateio'
    :param is_subscribe: subscribe or unsubscribe
    :return:
    '''
    symbol_send_list = []
    GEARS = EXCHANGE_GEARS[exchange]
    if exchange == 'bn':
        for symbol in symbols:
            symbol_send = trans_bn_symbols.get(symbol, symbol)
            symbol_send_list.append(
                "{}@depth{}@{}ms".format(symbol_send.replace("-", '').lower(), GEARS, INTERVAL))
        asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(
            ujson.dumps({
                "method": is_subscribe.upper(),
                "params": symbol_send_list,
                "id": random.randint(1, 10000)}
            )))
    if exchange == 'okex':
        for symbol in symbols:
            symbol_send = trans_okex_symbols.get(symbol, symbol)
            symbol_send_list.append({
                "channel": f"books{GEARS}",
                "instId": symbol_send
            })
        asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps({
            "op": is_subscribe,
            "args": symbol_send_list,
        })))
    if exchange == 'gate':
        for s in symbols:
            symbol = trans_gateio_symbols.get(s, s)
            symbol_send = {
                "time": int(time.time()),
                "channel": "spot.order_book",
                "event": is_subscribe,
                "payload": [symbol.replace("-", "_").upper(), f"{GEARS}", f"{INTERVAL}ms"]
            }
            asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps(symbol_send)))
    if exchange == 'hb':
        for symbol in symbols:
            symbol_send = trans_hb_symbols.get(symbol, symbol)
            symbol_send = symbol_send.replace("-", '').lower()
            param = 'sub' if is_subscribe == 'subscribe' else 'unsub'
            data = {
                f"{param}": "market.{}.mbp.refresh.{}".format(symbol_send, GEARS),
                "id": random.randint(1, 10000),
            }
            asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps(data)))
    if exchange == 'mxc':
        for symbol in symbols:
            symbol_send = trans_mexc_symbols.get(symbol, symbol)
            symbol = symbol_send.replace("-", "")
            symbol_send_list.append(
                f"spot@public.limit.depth.v3.api@{symbol}@{GEARS}")
        if symbol_send_list:
            sub = "SUBSCRIPTION" if is_subscribe == 'subscribe' else 'UNSUBSCRIPTION'
            await global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps({
                "method": sub,
                "params": symbol_send_list,
            }))
    if exchange == 'bitget':
        for symbol in symbols:
            symbol_send = trans_bitget_symbols.get(symbol, symbol)
            symbol_send_list.append({
                "instType": "SPOT",
                "channel": f"books{GEARS}",
                "instId": symbol_send
            })
        asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps({
            "op": is_subscribe,
            "args": symbol_send_list,
        })))
    if exchange == 'kraken':
        new_list = []
        for symbol in symbols:
            symbol_send = trans_kraken_symbols.get(symbol, symbol)
            new_list.append(symbol_send)
        s_data = {"method": "subscribe", "params": {"channel": "ticker", "symbol": new_list}}
        asyncio.create_task(global_variable.EXCHANGE_WS_INSTANCE[exchange].send(ujson.dumps(s_data)))
    if is_subscribe == 'unsubscribe':
        await asyncio.sleep(5)
        for symbol in symbols:
            symbol_send = symbol
            if exchange == 'bn':
                symbol_send = trans_bn_symbols.get(symbol, symbol)
            if exchange == 'okex':
                symbol_send = trans_okex_symbols.get(symbol, symbol)
            if exchange == 'gate':
                symbol_send = trans_gateio_symbols.get(symbol, symbol)
            if exchange == 'hb':
                symbol_send = trans_hb_symbols.get(symbol, symbol)
            if exchange == 'mxc':
                symbol_send = trans_mexc_symbols.get(symbol, symbol)
            if exchange == 'bitget':
                symbol_send = trans_bitget_symbols.get(symbol, symbol)
            if exchange == 'kraken':
                symbol_send = trans_kraken_symbols.get(symbol, symbol)
            try:
                logger.info(f'取消订阅，删除=> {exchange} {symbol_send}')
                del global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol_send]
                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
            except Exception as e:
                logger.error(f"{traceback.format_exc()}")
                continue


async def subscribe_ws():
    while True:
        try:
            await asyncio.sleep(5)
            for ex in WS_EXCHANGE_ACTIVE:
                logger.info(f'hedge symbols => 【{ex}】{list(global_variable.SHARE_MEMORY_WS_INSTANCE[ex].keys())}')
            for ex in WS_EXCHANGE_ACTIVE:
                msg = ''
                for k, v in global_variable.SHARE_MEMORY_WS_INSTANCE[ex].items():
                    msg += str(k) + ':' + str(v) + '\n'
                logger.info(f'hedge config =>【{ex}】{msg}\n')
            ws_depth_subscribe, ws_depth_unsubscribe = {}, {}
            for currency, hedge_config in global_variable.SHARE_SYMBOL_HEDGE_CONFIG.items():
                # 获取增减的交易所和币种
                hedge_exchanges = hedge_config.get('exchanges', {})
                older_exchanges = global_variable.SYMBOL_HEDGE_CONFIG_OLDER.get(currency, {}).get('exchanges', {})
                older_config = global_variable.SYMBOL_HEDGE_CONFIG_OLDER.get(currency, {})
                # 新的为True,旧的为False,增加订阅
                if hedge_config['status'] and older_config.get('status', '') is False:
                    for ex, value in hedge_exchanges.items():
                        if value['percent'] != 0:
                            symbol = value['symbol']
                            symbols = ws_depth_subscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_subscribe.update({ex: symbols})
                # 旧的为True,新的为False,减少订阅
                elif older_config.get('status', '') and hedge_config['status'] is False:
                    for ex, value in hedge_exchanges.items():
                        if value['percent'] != 0:
                            symbol = value['symbol']
                            symbols = ws_depth_subscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_unsubscribe.update({ex: symbols})
                else:
                    for ex, value in hedge_exchanges.items():
                        symbol = value['symbol']
                        # 增加新的配置，如果状态正常，权重不为0，增加订阅
                        if ex not in older_exchanges.keys() and hedge_config['status'] and value['percent'] != 0:
                            symbols = ws_depth_subscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_subscribe.update({ex: symbols})
                        # 修改的配置，如果新配置权重为0，旧配置不为0，减少订阅
                        if ex in older_exchanges.keys() and (
                                value['percent'] == 0 and older_exchanges[ex]['percent'] != 0):
                            symbols = ws_depth_unsubscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_unsubscribe.update({ex: symbols})
                    for ex, value in older_exchanges.items():
                        symbol = value['symbol']
                        # 删除币种某个交易所配置，并且就配置不为0，减少订阅
                        if ex not in hedge_exchanges.keys() and value['percent'] != 0:
                            symbols = ws_depth_unsubscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_unsubscribe.update({ex: symbols})
                        # 修改配置，如果旧配置权重为0，新配置不为0，增加订阅
                        if ex in hedge_exchanges.keys() and (
                                value['percent'] == 0 and hedge_exchanges[ex]['percent'] != 0):
                            symbol = hedge_exchanges[ex]['symbol']
                            symbols = ws_depth_subscribe.get(ex, [])
                            symbols.append(symbol)
                            ws_depth_subscribe.update({ex: symbols})

            # 删除币种配置的情况，取消当前币种的订阅
            for currency, hedge_config in global_variable.SYMBOL_HEDGE_CONFIG_OLDER.items():
                if currency not in list(global_variable.SHARE_SYMBOL_HEDGE_CONFIG.keys()):
                    currency_config = global_variable.SYMBOL_HEDGE_CONFIG_OLDER.get(currency, {})
                    currency_exchanges = currency_config.get('exchanges', {})
                    for ex, value in currency_exchanges.items():
                        symbol = value['symbol']
                        symbols = ws_depth_unsubscribe.get(ex, [])
                        symbols.append(symbol)
                        ws_depth_unsubscribe.update({ex: symbols})

            # 增减订阅
            logger.info('=' * 100)
            logger.info(f'增加 {ws_depth_subscribe}')
            logger.info(f'减少 {ws_depth_unsubscribe}')
            logger.info('=' * 100)
            for ex, symbols in ws_depth_subscribe.items():
                await update_ws_subscribe(symbols=symbols, exchange=ex, is_subscribe='subscribe')
            for ex, symbols in ws_depth_unsubscribe.items():
                await update_ws_subscribe(symbols=symbols, exchange=ex, is_subscribe='unsubscribe')

            # 将新配置更新到变量
            global_variable.SYMBOL_HEDGE_CONFIG_OLDER = copy.deepcopy(global_variable.SHARE_SYMBOL_HEDGE_CONFIG.data)
        except Exception as e:
            logger.error(f"{traceback.format_exc()}")
            await asyncio.sleep(5)
            continue


async def get_exchange_depth_amounts(exchange, symbol, price, side):
    logger.info(f'{symbol} | {exchange}| {side} | {price}')
    if not price:
        return 0
    now_time = int(time.time())
    gear_data = global_variable.SHARE_MEMORY_WS_INSTANCE.get(exchange, {}).get(symbol, {})
    try:
        if abs(now_time - gear_data.get('ts', 0)) > 60:
            GEARS = EXCHANGE_GEARS[exchange]
            data = await EXTERNAL_EXCHANGE_INSTANCES[exchange].depth(symbol, limit=GEARS)
            logger.info(f'{symbol} | {exchange}| {data}')
            asks, bids = data['asks'], data['bids']
        else:
            asks, bids = gear_data['asks'], gear_data['bids']
        depth_amount = 0
        if side == 'SELL':
            for bid in bids:
                if float(bid[0]) >= float(price):
                    depth_amount += float(bid[1])
        if side == "BUY":
            for ask in asks:
                if float(ask[0]) <= float(price):
                    depth_amount += float(ask[1])
        print(f'depth_amount {depth_amount}')
    except Exception as error:
        msg = f"{exchange} {symbol} {price} {side} {traceback.format_exc()}"
        logger.error(msg)
        await recode_error_msg(msg, server="spot_hedge")
        depth_amount = 0
    return depth_amount
