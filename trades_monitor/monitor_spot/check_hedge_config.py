import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from libs.send_tglegram_msg import send_telegram_async, push_msg
from scaffold.mysql import G_MysqlSession, Hedge_MysqlSession
import json
from libs import heartbeat, libs_config, libs_price_async, delisting_currency
import asyncio
from collections import defaultdict

price_symbol = libs_config.PRICE_SYMBOL_CONFIG
price_symbols_pair = []
depth_price_pair = []
for k, v in price_symbol.items():
    price_symbols_pair.append(v['price_symbol'])
    depth_price_pair.append(v['depth_price'])
all_symbols = set(list(price_symbol.keys()))
price_redis_db = libs_price_async.redis_db_market_price


async def compare_hedge():
    compare_dict = {'ethereum_1': 'uniswapv3', 'ethereum_2': 'uniswapv3', 'ethereum_3': 'uniswapv3'}
    sql = f''' select * from withdraw_deposit'''
    result2 = await G_MysqlSession.fetch_all(sql)
    symbol_hedge = {}
    for i in result2:
        if i[1] != 'None':
            data = []
            for ex in eval(i[1]):
                data.append(compare_dict.get(ex, ex))
            symbol_hedge[i[0]] = data
    sql = f''' select * from exchange_symbols_referrence'''
    result = await G_MysqlSession.fetch_all(sql)
    symbol_trade = {}
    for i in result:
        symbol_trade[i[0]] = eval(i[1])
    msg = '对冲交易所非参考交易所,请联系相关人员调整:\n'
    for currency in list(symbol_hedge.keys()):
        if currency in delisting_currency.off_spot_currency:
            continue
        try:
            com = set(symbol_hedge[currency]) & set(symbol_trade[currency])
        except:
            print(currency, '正在上线')
            continue
        if not com:
            if currency == 'SPCX':
                continue
            msg += f'【{currency}】对冲交易所: {symbol_hedge[currency]}   参考交易所: {",".join(symbol_trade[currency])}\n'
    print(msg)
    await heartbeat.i_live_well("对冲与对标交易所一致性", 61 * 10, 66)
    if msg != '对冲交易所非参考交易所,请联系相关人员调整:\n':
        await send_telegram_async(msg, 'warning')
        await push_msg('hedge_config', msg)
    else:
        await push_msg('hedge_config', '')


async def get_hedge_config():
    websea_hedge = {}
    hedge_style = defaultdict(dict)
    hedge_config = await Hedge_MysqlSession.fetch_all('select * from hedge_config')
    for config in hedge_config:
        symbol = config[0]
        config_li = json.loads(config[1])
        datas = []
        for ex, value in config_li['exchanges'].items():
            if float(value['percent']) != 0:
                datas.append(ex)
                hedge_style[symbol][ex] = value['hedge_style']
        websea_hedge[symbol] = datas
    return websea_hedge, hedge_style


# 当前币种对冲配置与对标交易所不匹配d
# 比如我们对标价格（包括市场价格和买卖一价格）对标的是bn ok 但是我们在ok对冲的，就是交易所有个对冲优先级，不是最高优先级需要报警，还有是faster方式对冲的需要提醒发出来
# bn ok gate mexc hb
async def hedge_config_monitor():
    hedge_priority = {'bn': 1, 'okex': 100, 'gate': 3, 'mxc': 100, 'hb': 100}
    hedge_config, hedge_style = await get_hedge_config()
    symbol_trades_redis = {}
    for symbol in all_symbols:
        symbol_trades_redis[symbol.split('-')[0]] = set((await price_redis_db.async_connection.hgetall(symbol)).keys())
    for symbol, config in symbol_trades_redis.items():
        symbol_trades_redis[symbol] = list(set([i.split('_')[0] for i in config]))
    msg = '！！当前币种对冲配置与对标交易所优先级（bn > ok > gate > mexc > hb）不匹配，请核对参数配置:\n'
    redis_priority = defaultdict(list)
    hedge_config_priority = defaultdict(list)
    for s, config in symbol_trades_redis.items():
        for i in config:
            redis_priority[s].append(hedge_priority.get(i, 100))
    for s, config in hedge_config.items():
        for i in config:
            hedge_config_priority[s].append(hedge_priority.get(i, 100))
    for s in hedge_config:
        if redis_priority[s] and min(redis_priority[s]) not in hedge_config_priority[s]:
            msg += f'【{s}】对冲配置非最高优先级交易所, 可调整对冲配置{hedge_config[s]} => {symbol_trades_redis[s]}\n'
    for symbol, style_config in hedge_style.items():
        for ex, style in style_config.items():
            if style in ['taker']:
                msg += f'【{symbol}】当前对冲交易所【{ex}】为faster对冲，请确认配置\n'
    print(msg)
    await heartbeat.i_live_well("对冲配置优先级检测", 61 * 10, 66)
    if msg != '！！当前币种对冲配置与对标交易所优先级（bn > ok > gate > mexc > hb）不匹配，请核对参数配置:\n':
        await send_telegram_async(msg, 'warning')
        await push_msg('hedge_config', msg)
    else:
        await push_msg('hedge_config', '')


async def main():
    await compare_hedge()
    await hedge_config_monitor()


if __name__ == '__main__':
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print('当前时间：', cu_time)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
