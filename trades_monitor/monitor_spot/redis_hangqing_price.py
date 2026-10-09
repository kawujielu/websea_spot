import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import threading
import time
import asyncio
import json
from collections import defaultdict
from libs import libs_config, libs_price_async
from libs import heartbeat
from libs.send_tglegram_msg import send_telegram_async, push_msg
from loguru import logger

SPOT_CURRENCY_CONFIG = libs_config.SPOT_CURRENCY_CONFIG
# 价差
PRICE_PERCENT = {}
DEFAULT_PRICE_PERCENT = 0.5
for key, value in SPOT_CURRENCY_CONFIG.items():
    PRICE_PERCENT[key] = 0.4 if value['dangerous_level'] <= 4 else 0.5
    if value.get("is_stable_coin"):
        PRICE_PERCENT[key] = 0.03

logger.info(f'PRICE_PERCENT: {PRICE_PERCENT}')

# 每轮价格获取间隔时间
PRICE_TIME_FLAG = 60
# 120MIN 价格列表
PRICE_SYMBOL_120MIN = defaultdict(list)

redis_price = libs_price_async.redis_db_market_price
redis_hangqing_config = libs_price_async.redis_db_control

hangqing_key = "spot_hangqing"


async def write_hangqing_redis(data):
    data = {k: json.dumps(
        {'hangqing': v, 'trigger_date': time.strftime('%Y年%m月%d日 %H:%M:%S', time.localtime(int(time.time())))})
        for k, v in data.items()}
    res = await redis_hangqing_config.async_connection.hmset(hangqing_key, data)
    return res


async def get_hangqing_redis_flag(symbol):
    data = await redis_hangqing_config.async_connection.hget(hangqing_key, symbol)
    res = json.loads(data)['hangqing'] if data else True
    return res


async def write_hangqing_config():
    global PRICE_SYMBOL_120MIN
    while True:
        msg = '现货极端行情=>\n'
        redis_hangqing_data = await redis_hangqing_config.async_connection.hgetall(hangqing_key)
        cur_hangqing_currencies = redis_hangqing_data.keys()

        for symbol, values in PRICE_SYMBOL_120MIN.items():
            values_max = max(values)
            values_min = min(values)
            max_index = values.index(values_max)
            min_index = values.index(values_min)
            if min_index < max_index:
                # 上涨
                flag = 'up'
                percent = (values_max - values_min) / values_min
            else:
                # 下跌
                flag = 'down'
                percent = (values_max - values_min) / values_max
            currency = symbol.split('-')[0]
            if percent >= PRICE_PERCENT.get(symbol.split('-')[0], DEFAULT_PRICE_PERCENT) and flag == 'down':
                percent = round(percent * 100, 2)
                
                # 单独针对稳定币的报警过滤
                if currency in ["EURQ", "EURR"] and percent < 3:
                    continue

                # 单独针对稳定币的报警过滤
                if currency in ["EURQ", "EURR"] and percent < 3:
                    continue

                # 如果redis已经有数据了就暂时不写入
                if currency in cur_hangqing_currencies:
                    logger.info(f"{currency}, {flag} 已经触发行情中")
                else:
                    logger.info(f'新增行情=> {currency=} {flag} {percent}% {values_max=} {values_min}')
                    msg += f"{currency}发现行情, percent: {percent}%\n"
                    await write_hangqing_redis({currency: True})
            elif currency in cur_hangqing_currencies:
                logger.info(f'解除行情=> {currency} {flag} {percent}%')
                msg += f"{currency}解除行情, {flag} percent: {percent}%\n"
                await redis_hangqing_config.async_connection.hdel(hangqing_key, currency)
        if msg != '现货极端行情=>\n':
            logger.info(f'{msg}')
            await send_telegram_async(msg, 'send_telegram_important_msg_url')
            await push_msg('bb_market', msg)
        else:
            logger.info(f'没有检测到行情触发')

        await asyncio.sleep(PRICE_TIME_FLAG)


async def price_symbol(symbol):
    global PRICE_SYMBOL_120MIN
    res = await redis_price.async_connection.hgetall(symbol)
    values = [float(res[k]) for k in res if 'update' not in k]
    PRICE_SYMBOL_120MIN[symbol] = PRICE_SYMBOL_120MIN.get(symbol, [])
    PRICE_SYMBOL_120MIN[symbol].append(min(values))
    PRICE_SYMBOL_120MIN[symbol].append(max(values))
    PRICE_SYMBOL_120MIN[symbol] = PRICE_SYMBOL_120MIN[symbol][-2*60*2:]


async def run():
    while True:
        symbols = await redis_price.async_connection.keys()
        tasks = [asyncio.create_task(price_symbol(symbol)) for symbol in symbols]
        for t in tasks:
            await t
        await heartbeat.i_live_well("redis行情", 60 * 2, 66)
        await asyncio.sleep(PRICE_TIME_FLAG)


if __name__ == '__main__':
    thread_1 = threading.Thread(target=asyncio.run, args=(write_hangqing_config(),), name='hangqing_thread')
    thread_2 = threading.Thread(target=asyncio.run, args=(run(),), name='price_thread')
    thread_li = [thread_1, thread_2]
    for i in thread_li:
        i.start()
    for i in thread_li:
        i.join()
