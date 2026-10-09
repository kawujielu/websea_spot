# coding=utf-8
import copy

import pandas as pd
import datetime, time, asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage
from spot.spot_setting import getRate, get_symbols
from config import monitor

from exchange.restful_api.abc_interfaces import AINTERFACES
from exchange.restful_api.binance import BinanceApi
from config import infor_hedge
from libs.auto_wd import send_wd_signal
from libs.database.getredis import rs_wd_instance
from loguru import logger


a_interfaces = AINTERFACES()
_bn_api = BinanceApi(**infor_hedge.config_exchange['hedge']['bn']['apikey'])
sleep_timeout = {'long': 60 * 20, 'short': 60 * 10}
currency_ids = {}
long_ts = 60 * 60 * 2
short_ts = 60 * 60 * 0.5
ts = {'long': long_ts, 'short': short_ts}
_DEP_SEEN_TTL = int(long_ts) + 3600  # 覆盖 long 窗口，避免同单反复写信号
CONFIG = {'USDT': {
    'long': {'count': 10, 'amount_u': 10000 * 100},
    'short': {'count': 10, 'amount_u': 10000 * 100}}
}

CONFIG_OTHER = {
    'long': {'count': 5, 'amount_u': 10000},
    'short': {'count': 10, 'amount_u': 20000}}
# 大额充值写 auto_wd_signal 前：外盘 BN 余额 >= 阈值则跳过
BN_SKIP_WD_THRESHOLDS = {
    'BTC': 10,
    'ETH': 10,
    'SOL': 10,
    'BNB': 10,
    'TRX': 3000,
    'HOME': 100000,
}
last_long_tg_msg = {'充值': [], "提币": []}
last_short_tg_msg = {'充值': [], "提币": []}


async def _bn_balance_enough_to_skip(curr: str) -> bool:
    """外盘 BN 该币余额达到阈值则返回 True（应跳过提币信号）。"""
    threshold = BN_SKIP_WD_THRESHOLDS.get(str(curr).upper())
    if threshold is None:
        return False
    try:
        bn_wallet = await _bn_api.wallet()
        if not isinstance(bn_wallet, dict):
            return False
        bal = float(bn_wallet.get(curr, bn_wallet.get(str(curr).upper(), 0)) or 0)
        if bal >= threshold:
            logger.info(f"bn {curr}余额{bal}>={threshold}，跳过auto_wd_signal")
            return True
    except Exception as e:
        logger.error(f"查询bn {curr}余额失败: {e}")
    return False


async def _unseen_deposit_amt(raw_info):
    """按充值单 id 过滤已写过信号的记录，返回 (新数量合计, 新id列表)。"""
    r = rs_wd_instance.async_connection
    amt, ids = 0.0, []
    for uid, a, did in raw_info:
        if uid in (196, "196", 1, "1"):
            continue
        if not await r.exists(f"auto_wd_dep_seen:{did}"):
            amt += a
            ids.append(did)
    return amt, ids


async def _mark_deposit_seen(ids):
    r = rs_wd_instance.async_connection
    for did in ids:
        await r.set(f"auto_wd_dep_seen:{did}", 1, ex=_DEP_SEEN_TTL, nx=True)


async def dict_data(k, dict_deposit_data, rate, side):
    global last_short_tg_msg, last_long_tg_msg
    msg = ""
    now_k_tg_msg = []
    # COUNT =
    # AMOUNT_U, TS,
    mm = {curr: v[k] for curr, v in CONFIG.items()}
    mm['other'] = CONFIG_OTHER[k]
    TS = ts[k]
    if dict_deposit_data:
        dict_deposit_short_copy = copy.deepcopy(dict_deposit_data)
        for curr, v in dict_deposit_short_copy.items():
            price = rate.get(f'{curr}-USDT', 0)
            dict_deposit_data[curr]['amount_u'] = v['amount'] * price
            dict_deposit_data[curr]['rate'] = price
            dict_deposit_data[curr]['raw_info'] = v['info']
            info = {}
            for i in v['info']:
                info[i[0]] = {'amount': info.get(i[0], {}).get('amount', 0) + i[1],
                              'amount_u': info.get(i[0], {}).get('amount_u', 0) + i[1] * price,
                              'count': info.get(i[0], {}).get('count', 0) + 1,
                              }
            dict_deposit_data[curr]['info'] = info
        for curr, v in dict_deposit_data.items():
            COUNT = mm[curr]['count'] if mm.get(curr) else mm['other']['count']
            AMOUNT_U = mm[curr]['amount_u'] if mm.get(curr) else mm['other']['amount_u']
            if curr in ['WBS', "MT", "MH"]:
                continue

            if v['amount_u'] >= AMOUNT_U or (v['count'] >= COUNT and v['amount_u'] > AMOUNT_U / 2) or v['rate'] == 0:
                msg += f"【{curr}】 数量:{round(v['amount'], 2)} 价值:{int(v['amount_u'])}U {side}笔数:{v['count']} 人数:{len(v['info'])}\n"
                deposit_sum = 0
                for id, j in v['info'].items():
                    # if j['amount_u'] >= AMOUNT_U or j['count'] >= COUNT or v['rate'] == 0:
                    #     msg += f" ●  id:{id} 数量:{round(j['amount'], 2)} 价值:{int(j['amount_u'])}U {side}笔数:{j['count']}\n"
                    #     now_k_tg_msg.append(f"{side}{id}{round(j['amount'], 2)}")
                    if id not in [196, "196", 1, "1"]:
                        deposit_sum += int(j['amount_u'])
                    msg += f" ●  id:{id} 数量:{round(j['amount'], 2)} 价值:{int(j['amount_u'])}U {side}笔数:{j['count']}\n"
                    now_k_tg_msg.append(f"{side}{id}{round(j['amount'], 2)}")
                if side == '充值' and deposit_sum > AMOUNT_U and curr not in ["USDT", "USDC"]:
                    new_amt, new_ids = await _unseen_deposit_amt(v.get('raw_info') or [])
                    if new_amt > 0:
                        msg += "！！！！资产确认是否需要提前提币备付对冲 @kawujielu_sky @TB147258 "
                        wd_msg = f"检测到用户大额的充值记录： {curr} 充值 {round(new_amt, 2)} ！ @kawujielu_sky @TB147258 "
                        logger.info(wd_msg)
                        sendmessage.send_telegram_msg_mdv2(message=wd_msg, ser='spot_hedge')
                        skip_wd = await _bn_balance_enough_to_skip(curr)
                        if not skip_wd:
                            await _mark_deposit_seen(new_ids)
                            await send_wd_signal(curr, round(new_amt, 4), 1)
    last_tg_msg = last_long_tg_msg[side] if k == 'long' else last_short_tg_msg[side]
    mess_quant_web = ""
    if msg:
        if set(now_k_tg_msg) != set(last_tg_msg):
            ts_msg = f"{int(TS / 60)}分钟" if TS < 60 * 60 else f"{int(TS / 60 / 60)}小时"
            msg = f"\\#*ABC{side}信息* {ts_msg}内{side}记录 {mm} 满足(count and amount_u/2) or amount_u or 获取不到价格 ({int(sleep_timeout[k] / 60)}min/次)\n" + msg
            mess_quant_web = msg
            # msg = f"\\#*ABC{side}信息* {ts_msg}内{side}记录 {side}笔数>{COUNT} or {side}金额>{AMOUNT_U}U or 获取不到价格 ({int(sleep_timeout / 60)}min/次)\n" + msg
            # msg = msg.replace('(', '\\(').replace(')', '\\)').replace('-', '\\-').replace('.', '\\.')
            sendmessage.send_telegram_msg_mdv2(message=msg, ser='spot_info')
    monitor.get_a_monitor(event_name='hy_freeze', msg=mess_quant_web)
    if k == 'long':
        last_long_tg_msg[side] = now_k_tg_msg
    else:
        last_short_tg_msg[side] = now_k_tg_msg


async def get_currency_ids():
    d = await a_interfaces.currency_list(currency=None)
    currency_ids = {i['id']: i['name'] for i in d['result']}
    return currency_ids


async def deposit_withdraw_list(long_time, short_time, type, flag):
    global currency_ids
    page_size = 20
    dict_deposit_short = {}
    dict_deposit_long = {}

    end_time = int(time.time())
    start_time_long = int(end_time - long_time)
    start_time_short = int(end_time - short_time)

    for page in range(1, 100):
        # res = await a_interfaces.get_deposit_list(page, page_size, start_time=start_time_long, end_time=end_time)
        res = await getattr(a_interfaces, type)(page, page_size, start_time=start_time_long, end_time=end_time)
        if res.get('errno', "") == 0:
            for i in res['result']['data']:
                if (i['status'] not in [2, 11, 12] and 'withdraw' in type) or (i['status'] not in [11, 12] and 'deposit' in type):
                    if 'withdraw' in type:
                        currency = currency_ids.get(i.get('currency', 0))
                        if not currency:
                            currency_ids = await get_currency_ids()
                            currency = currency_ids.get(i.get('currency', 0))
                        i['currency_name'] = currency
                        i['create_time'] = i['ctime']
                        i['userId'] = i['user_id']
                    dep_id = str(i.get('id') or i.get('tx_hash') or f"{i['userId']}_{i.get('create_time')}_{i['amount']}")
                    row = [i['userId'], float(i['amount']), dep_id]
                    dict_deposit_long[i['currency_name']] = {
                        'amount': dict_deposit_long.get(i['currency_name'], {}).get('amount', 0) + float(i['amount']),
                        'count': dict_deposit_long.get(i['currency_name'], {}).get('count', 0) + 1,
                        'info': dict_deposit_long.get(i['currency_name'], {}).get('info', [])
                    }
                    dict_deposit_long[i['currency_name']]['info'].append(row)
                    if start_time_short <= i['create_time']:
                        dict_deposit_short[i['currency_name']] = {
                            'amount': dict_deposit_short.get(i['currency_name'], {}).get('amount', 0) + float(i['amount']),
                            'count': dict_deposit_short.get(i['currency_name'], {}).get('count', 0) + 1,
                            'info': dict_deposit_short.get(i['currency_name'], {}).get('info', [])
                        }
                        dict_deposit_short[i['currency_name']]['info'].append(row)
                    # print('dict_deposit_short', dict_deposit_short)
                    # print('dict_deposit_long', dict_deposit_long)
            if len(res['result']['data']) < page:
                break
    currency = list(dict_deposit_short.keys()) + list(dict_deposit_long.keys())
    symbols = [i + '-USDT' for i in set(currency)]
    rate = await getRate(symbols)
    side = '充值' if 'deposit' in type else "提币"
    dict_deposit = {'long': dict_deposit_long, 'short': dict_deposit_short}

    for k, v in dict_deposit.items():
        if ('long' == k and flag) or 'short' == k:
            await dict_data(k, v, rate, side=side)

    # await dict_data(dict_deposit_short, rate, COUNT=5, AMOUNT_U=5000, TS=short_time, side=side)
    # await dict_data(dict_deposit_long, rate, COUNT=10, AMOUNT_U=10000, TS=long_time, side=side)


async def spot_run():
    start_time = 0
    while True:
        try:
            flag = 1 if (abs(time.time() - start_time) >= sleep_timeout['long'] or start_time == 0) else 0
            start_time = time.time() if flag else start_time
            for ty in ['get_deposit_list', 'get_withdraw_list']:
                await deposit_withdraw_list(long_time=long_ts, short_time=short_ts, type=ty, flag=flag)
            await heartbeat.i_live_well(server='abc用户充提监控', frequency=60 * 60 * 2, index=34)

            print('订单成交量监控 , ok')
            await asyncio.sleep(sleep_timeout['short'])

        except:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sendmessage.send_telegram_msg(f'{now} | error：abc充值监控 ', 'Alarm')
            print(f'{now} | error : abc充值监控 ')
            await asyncio.sleep(sleep_timeout['short'] / 2)


if __name__ == '__main__':
    asyncio.run(spot_run())
