# coding=utf-8
import asyncio
import loguru
import pandas as pd
import numpy as np
import copy, time, datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getredis import get_redis, get_redis_contract
from config import monitor
from libs.heartbeat import i_live_well
from libs.sendmessage import send_telegram_msg
from config.infor import SYMBOLS_PAIR_DANGEROUS_LEVEL
from config.infor_contract import SYMBOLS_CONTRACT_PAIR_DANGEROUS_LEVEL

# PRICE_PRO = 0.0035
# PRICE_PRO_MAX = PRICE_PRO * 2

# PRICE_PRO_ABC = 0.02
# PRICE_PRO_ABC_MAX = PRICE_PRO_ABC * 2

TIMEOUT = 6
TIMEOUT_MAX = TIMEOUT * 2

TIMEOUT_ME = 60
TIMEOUT_ME_MAX = TIMEOUT_ME * 2
TIMEOUT_ABC_ONLY = 60 * 10
TIMEOUT_ABC_ONLY_MAX = TIMEOUT_ABC_ONLY * 2

sleep_timeout = 60 * 1

staging = []

PRO_LEVEL = {
    1: 0.005,
    3: 0.008,
    10: 0.006
}
# 1号库 现货
# 2号库 合约

protem = {f'1号库时间超时>{TIMEOUT}s': {},
          f"1号库对标交易所之间的价差": {},
          f"2号库价差:对标价格与abc标记价格的价差": {},
          f"2号库外部时间超时{TIMEOUT_ME}s": {},
          f"2号库abc时间超时{TIMEOUT_ABC_ONLY}s": {},
          f"2号库价差:对标交易所价格的价差": {},
          f"1和2号库价差比较": {}
          }
# LAST_SYMBOLS_MESSAGE, SYMBOLS_MESSAGE = {}, {}
last_symbols_message, symbols_message = {}, {}


def get_level(level):
    for k, v in PRO_LEVEL.items():
        if level <= k:
            return v


SYMBOL_SPEC_PERCENT = {
    "GOUT-USDT": 0.03,
    "GOAT-USDT": 0.03,
    "OKB-USDT": 0.01,
    "SEND-USDT": 0.03,
    "SNAP-USDT": 0.03,
    "ALCH-USDT": 0.02,
}

async def get_redis_1(temporary, protem_max):
    symbols = await get_redis.keys()
    now_time = time.time()
    msg_update, msg_price = {}, {}
    redis_price_1 = {}
    error = []
    for s in symbols:
        try:
            res = await get_redis.hgetall(s)
            price = {k: float(v) for k, v in res.items() if 'update' not in k}
            update = {k: int(v) for k, v in res.items() if 'update' in k}
            pro_price = max(price.values()) / min(price.values()) - 1
            redis_price_1[s] = price
            level = SYMBOLS_PAIR_DANGEROUS_LEVEL.get(s, 1)
            PRICE_PRO = get_level(level)
            cur_hour = datetime.datetime.now().hour
            cur_min = datetime.datetime.now().minute
            if not(cur_hour % 5 == 0 and cur_min < 10):
                PRICE_PRO = SYMBOL_SPEC_PERCENT.get(s, PRICE_PRO)
            PRICE_PRO_MAX = PRICE_PRO * 2
            if pro_price > PRICE_PRO:
                aa = {k: v for k, v in price.items() if v in [max(price.values()), min(price.values())]}
                msg_price[s] = f"{s}:价差:{round(pro_price * 100, 2)}% 等级:{level} {aa}\n"

            timeout = {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT}
            if timeout:
                aa = {k: int(now_time - v) for k, v in timeout.items()}
                msg_update[s] = f"{s}: 时间超时{aa} 具体数据:{timeout}\n"

            #   最大值 强制报警
            if pro_price > PRICE_PRO_MAX:
                protem_max[f"1号库对标交易所之间的价差"].append(s)
            if {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT_MAX}:
                protem_max[f"1号库时间超时>{TIMEOUT}s"].append(s)

        except Exception as e:
            loguru.logger.info(f'error-redis_1,{s} {e}')
            error.append(s)

    if msg_update:
        temporary[f"1号库时间超时>{TIMEOUT}s"] = msg_update
    if msg_price:
        temporary[f"1号库对标交易所之间的价差"] = msg_price
    return redis_price_1, temporary, protem_max, error


async def get_redis_2(temporary, protem_max):
    """
    外部价格 均值 /  price > 千一
    time.time() - 时间  > 10s 报警
    外部交易所 max / min > 千 1
    """
    symbols = await get_redis_contract.keys()
    now_time = time.time()
    msg_price = {}
    msg_update = {}
    msg_update_abc = {}
    msg_price_abc = {}
    error = []

    redis_price_2 = {}
    for s in symbols:
        try:
            res = await get_redis_contract.hgetall(s)
            redis_price_2[s] = {k: float(v) for k, v in res.items() if '_price' in k}
            price = {k: float(v) for k, v in res.items() if 'price' == k}
            price_ex = {k: float(v) for k, v in res.items() if '_price' in k}
            update = {k: int(v) for k, v in res.items() if 'update' in k}
            pro_price_ex = max(price_ex.values()) / min(price_ex.values()) - 1
            price_ex_avg = list(price_ex.values()) + list(price.values())
            pro_price = max(price_ex_avg) / min(price_ex_avg) - 1
            level = SYMBOLS_CONTRACT_PAIR_DANGEROUS_LEVEL.get(s, 1)
            PRICE_PRO = get_level(level)
            PRICE_PRO_MAX = PRICE_PRO * 2

            PRICE_PRO_ABC = PRICE_PRO
            PRICE_PRO_ABC_MAX = PRICE_PRO_MAX

            if pro_price > PRICE_PRO_ABC:
                msg_price_abc[s] = f"{s}:abc与外部价差:{round(pro_price * 100, 2)}%  等级:{level} {price}{price_ex}\n"

            if pro_price_ex > PRICE_PRO:
                msg_price[s] = f"{s}:外部价差:{round(pro_price_ex * 100, 2)}% 等级:{level} {price_ex}\n"

            if any("_update" in i for i in update.keys()):
                timeout = {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT_ME and '_update' in k}
                if timeout:
                    aa = {k: int(now_time - v) for k, v in timeout.items()}
                    msg_update[s] = f"{s}: 时间超时{aa} {timeout}\n"
            if any("update" == i for i in update.keys()):
                timeout = {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT_ABC_ONLY and '_update' not in k}
                if timeout:
                    aa = {k: int(now_time - v) for k, v in timeout.items()}
                    msg_update_abc[s] = f"{s}: 时间超时{aa} {timeout}\n"

            #   最大值 强制报警
            if pro_price > PRICE_PRO_ABC_MAX:
                protem_max[f"2号库价差:对标价格与abc标记价格的价差"].append(s)
            if pro_price_ex > PRICE_PRO_MAX:
                protem_max[f"2号库价差:对标交易所价格的价差"].append(s)

            if {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT_ME_MAX and '_update' in k}:
                protem_max[f"2号库外部时间超时{TIMEOUT_ME}s"].append(s)

            if {k: v for k, v in update.items() if abs(now_time - v) > TIMEOUT_ABC_ONLY_MAX and '_update' not in k}:
                protem_max[f"2号库abc时间超时{TIMEOUT_ABC_ONLY}s"].append(s)


        except Exception as e:
            loguru.logger.info(f'error-redis_2,{s} {e}')
            error.append(s)
    if msg_price_abc:
        temporary[f"2号库价差:对标价格与abc标记价格的价差"] = msg_price_abc

    if msg_update:
        temporary[f"2号库外部时间超时{TIMEOUT_ME}s"] = msg_update
    if msg_update_abc:
        temporary[f"2号库abc时间超时{TIMEOUT_ABC_ONLY}s"] = msg_update_abc

    if msg_price:
        temporary[f"2号库价差:对标交易所价格的价差"] = msg_price
    return redis_price_2, temporary, protem_max, error


async def get_redis_1_to_2(redis_price_1, redis_price_2, temporary, protem_max):
    """
    1号库均价 / 2号库均价 > 千一  或者 2号库均价 / 1号库均价 > 千一
    """
    symbols = set(redis_price_1.keys()) & set(redis_price_2.keys())
    msg_price = {}
    for s in symbols:
        d = list(redis_price_1[s].values()) + list(redis_price_2[s].values())
        pro = max(d) / min(d) - 1

        level = max(SYMBOLS_PAIR_DANGEROUS_LEVEL.get(s, 1), SYMBOLS_CONTRACT_PAIR_DANGEROUS_LEVEL.get(s, 1))
        PRICE_PRO = get_level(level)
        PRICE_PRO_MAX = PRICE_PRO * 2

        if pro > PRICE_PRO:
            msg_price[s] = f"{s}:1和2号库价差:{round(pro * 100, 2)}%  等级:{level} 1号库{redis_price_1[s]} 2号库{redis_price_2[s]}\n"

        if pro > PRICE_PRO_MAX:
            protem_max[f"1和2号库价差比较"].append(s)

    if msg_price:
        temporary[f"1和2号库价差比较"] = msg_price
    return temporary, protem_max


def get_staging(staging, protem_max):
    global last_symbols_message
    staging = staging[-3:]
    message = ""
    mess_quant_web = ""
    symbols_message = {k: set() for k, v in protem.items()}
    if len(staging) == 3:
        [first, second, third] = staging
        for k, v in third.items():
            msg = ""
            for s, j in v.items():
                if (s in first[k].keys() and s in second[k].keys()) or s in protem_max[k]:
                    msg += j
                    symbols_message[k].add(s)
            if msg:
                d = "🩸🩸🩸" if "超时" in k else "⚠️️️"
                message += f"{d}️{k}\n{msg}"
        if message and symbols_message != last_symbols_message:
            l = "、".join([f"<={k}:{v * 100}%" for k, v in PRO_LEVEL.items()])
            message = f"连续三次超过设置参数，{l} ({int(sleep_timeout / 60)}min/次)\n" + message
            send_telegram_msg(message=message, ser='redis_price')
            last_symbols_message = copy.deepcopy(symbols_message)
            mess_quant_web = message
    monitor.get_a_monitor(event_name='redis_price', msg=mess_quant_web)

async def spot_run():
    while True:
        try:
            temporary = copy.deepcopy(protem)
            protem_max = {k: [] for k, v in protem.items()}
            redis_price_2, temporary, protem_max, error_2 = await get_redis_2(temporary, protem_max)
            redis_price_1, temporary, protem_max, error_1 = await get_redis_1(temporary, protem_max)
            temporary, protem_max = await get_redis_1_to_2(redis_price_1, redis_price_2, temporary, protem_max)
            staging.append(temporary)
            get_staging(staging, protem_max)

            if error_1 or error_2:
                msg1 = f"1号库币对报错 {error_1}" if error_1 else ""
                msg2 = f"2号库币对报错 {error_2}" if error_2 else ""
                send_telegram_msg(message=f"redis检测币对异常，需要排查:{msg1} {msg2}", ser='redis_price')

            await i_live_well(server='redis价差监控', frequency=60 * 15, index=34)
            await asyncio.sleep(sleep_timeout)
        except BaseException as e:
            mess = f'error：redis价差监控-spot_redis_price-->{e}'
            send_telegram_msg(mess, ser='Alarm')

            await asyncio.sleep(sleep_timeout / 2)


if __name__ == "__main__":
    asyncio.run(spot_run())
