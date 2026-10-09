import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from libs.send_tglegram_msg import send_telegram_async, push_msg
from libs import heartbeat, libs_config, libs_price_async
import asyncio

price_symbol = libs_config.PRICE_SYMBOL_CONFIG
price_symbols_pair = []
depth_price_pair = []
dex_price_pair = []
for k, v in price_symbol.items():
    price_data, depth_data = {}, {}
    for price_ex in list(v['price_symbol'].keys()):
        price_data = {price_ex: k}
        price_symbols_pair.append(price_data)
    for depth_ex in list(v['depth_price'].keys()):
        depth_data = {depth_ex: k}
        depth_price_pair.append(depth_data)
    for dex_ex in list(v['dex_price'].keys()):
        dex_data = {dex_ex: k}
        dex_price_pair.append(dex_data)
all_symbols = set(list(price_symbol.keys()))

contract_price_symbol = libs_config.CONTRACT_PRICE_SYMBOL_CONFIG
contract_price_symbols_pair = []
contract_price_pair = []
for k, v in contract_price_symbol.items():
    for price_ex in list(v['price_symbol'].keys()):
        price_data = {price_ex: k}
        contract_price_symbols_pair.append(price_data)
    for contract_ex in list(v['contract_price_symbol'].keys()):
        contract_price_data = {contract_ex: k}
        contract_price_pair.append(contract_price_data)
contract_all_symbols = set(list(contract_price_symbol.keys()))

price_redis_db = libs_price_async.redis_db_market_price
price_contract_redis_db = libs_price_async.redis_db_contract_price
price_heart = []


# --------------------------- 检查redis交相同易对对标价格是否和配置 ---------------------------

async def check_trade_price():
    symbol_trades = {}
    symbol_trades_redis = {}
    redis_symbol = set(await price_redis_db.async_connection.keys())
    for symbol in redis_symbol:
        symbol_trades_redis[symbol] = set((await price_redis_db.async_connection.hgetall(symbol)).keys())

    for exchange_symbol in price_symbols_pair:
        for exchange, symbol in exchange_symbol.items():
            if symbol in symbol_trades:
                symbol_trades[symbol].add(exchange)
                symbol_trades[symbol].add(exchange + '_update')
            else:
                symbol_trades[symbol] = {exchange, exchange + '_update'}
    for exchange_symbol in depth_price_pair:
        for exchange, symbol in exchange_symbol.items():
            if symbol in symbol_trades:
                symbol_trades[symbol].add("{}_depth".format(exchange))
                symbol_trades[symbol].add("{}_depth_update".format(exchange))
            else:
                symbol_trades[symbol] = {"{}_depth".format(exchange), "{}_depth_update".format(exchange)}
    for exchange_symbol in dex_price_pair:
        for exchange, symbol in exchange_symbol.items():
            if symbol in symbol_trades:
                symbol_trades[symbol].add(exchange)
                symbol_trades[symbol].add(exchange + '_update')
            else:
                symbol_trades[symbol] = {exchange, exchange + '_update'}
    diff_keys = set(symbol_trades_redis.keys()) ^ set(symbol_trades.keys())
    msg = '！！！非常紧急，现货参考交易所与redis数据不一致,请联系相关人员进行修改:\n'
    print('diff_keys', diff_keys)
    if diff_keys:
        diff = list(diff_keys)
        for i in diff:
            try:
                re = symbol_trades[i]
            except (KeyError):
                datas = list(symbol_trades_redis[i])
                msg += f'【{i}】需删除redis数据key值 {datas}\n'
            try:
                re = symbol_trades_redis[i]
            except (KeyError):
                datas = list(symbol_trades[i])
                msg += f'【{i}】需添加redis数据key值 {datas} \n'
    for symbol in all_symbols:
        symbol_trades_redis[symbol] = set((await price_redis_db.async_connection.hgetall(symbol)).keys())
    for s in symbol_trades:
        diff = symbol_trades[s] ^ symbol_trades_redis[s]
        if diff:
            symbol_trade = list(symbol_trades[s])
            symbol_trade_redis = list(symbol_trades_redis[s])
            msg += f'【{s}】需修改redis数据key值 {symbol_trade_redis} ==> {symbol_trade}\n'
    print(msg)
    price_heart.append('spot')
    if msg != '！！！非常紧急，现货参考交易所与redis数据不一致,请联系相关人员进行修改:\n':
        msg_len = len(msg)
        for i in range(0, msg_len, 4000):
            content = msg[i:i + 4000]
            await send_telegram_async(content, 'warning')
        await push_msg('redis_price', msg)
    else:
        await push_msg('redis_price', '')


async def check_trade_price_contract():
    symbol_trades = {}
    symbol_trades_redis = {}
    redis_symbol = set(await price_contract_redis_db.async_connection.keys())
    for symbol in redis_symbol:
        symbol_trades_redis[symbol] = set((await price_contract_redis_db.async_connection.hgetall(symbol)).keys())

    for exchange_symbol in contract_price_symbols_pair:
        for exchange, symbol in exchange_symbol.items():
            if symbol in symbol_trades:
                symbol_trades[symbol].add(exchange + '_price')
                symbol_trades[symbol].add(exchange + '_update')
            else:
                symbol_trades[symbol] = {exchange + '_price', exchange + '_update'}
    for exchange_symbol in contract_price_pair:
        for exchange, symbol in exchange_symbol.items():
            if symbol in symbol_trades:
                symbol_trades[symbol].add('c-' + exchange + '_price')
                symbol_trades[symbol].add('c-' + exchange + '_update')
            else:
                symbol_trades[symbol] = {'c-' + exchange + '_price', 'c-' + exchange + '_update'}
    for symbol, config in symbol_trades_redis.items():
        re = set()
        for info in config:
            if info not in ['price', 'update']:
                re.add(info)
        symbol_trades_redis[symbol] = re
    diff_keys = set(symbol_trades_redis.keys()) ^ set(symbol_trades.keys())
    msg = '！！！非常紧急，合约参考交易所与redis数据不一致,请联系相关人员进行修改:\n'
    print('diff_keys', diff_keys)
    if diff_keys:
        diff = list(diff_keys)
        for i in diff:
            try:
                re = symbol_trades[i]
            except (KeyError):
                datas = list(symbol_trades_redis[i])
                msg += f'【{i}】需删除redis数据key值 {datas}\n'
            try:
                re = symbol_trades_redis[i]
            except (KeyError):
                datas = list(symbol_trades[i])
                msg += f'【{i}】需添加redis数据key值 {datas} \n'
    for s in symbol_trades:
        diff = symbol_trades[s] ^ symbol_trades_redis[s]
        if diff:
            symbol_trade = list(symbol_trades[s])
            symbol_trade_redis = list(symbol_trades_redis[s])
            msg += f'【{s}】需修改redis数据key值 {symbol_trade_redis} ==> {symbol_trade}\n'
    print(msg)
    price_heart.append('contract')
    if msg != '！！！非常紧急，合约参考交易所与redis数据不一致,请联系相关人员进行修改:\n':
        msg_len = len(msg)
        for i in range(0, msg_len, 4000):
            content = msg[i:i + 4000]
            await send_telegram_async(content, 'warning')
        await push_msg('redis_price', msg)
    else:
        await push_msg('redis_price', '')


async def main():
    await check_trade_price()
    await check_trade_price_contract()
    err_msg = []
    for i in ['spot', 'contract']:
        if i not in price_heart:
            err_msg.append(i)
    if err_msg:
        await heartbeat.i_live_not_well(err_msg, "redis价格与对标配置一致性", 61 * 5, 66)
    else:
        await heartbeat.i_live_well("redis价格与对标配置一致性", 61 * 5, 66)


if __name__ == '__main__':
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print('当前时间：', cu_time)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
