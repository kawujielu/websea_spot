#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import traceback
import datetime, time
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.infor_contract import contract_account, SYMBOLS_CONTRACT_PAIR, acc_id_contract
from exchange.restful_api.abc_interfaces import AINTERFACES
from contract.contract_setting import get_symbols_details, getRate, sleep_time, CAPITAL_RATE_PARAM, get_capital_rate_param
from libs import sendmessage, heartbeat
from exchange.restful_api.abc_contract import AApi
from config import monitor

a_interfaces = AINTERFACES()
aapi = AApi()
FACE_VALUE = {}
# PROFIT_LOSS = 100
DIRECTION_AMOUNT_U = 10000
PROFIT_LOSS = 500
NUM = 10
PROFIT_LOSS_ALL = 50

fetch_timeout = 60 * 20


def get_face_value():
    global FACE_VALUE
    res = get_symbols_details()
    FACE_VALUE.update({i['symbol']: float(i['contract_size']) for i in res})


async def get_positon():
    rate = await getRate(SYMBOLS_CONTRACT_PAIR)

    async def position(rate, is_full, position_type):
        net_position = {}
        res = await a_interfaces.contract_position(symbol=None, self_user=1, is_full=is_full)
        res = res.get('result', {}).get('data', {})
        if res:
            for k, v in res.items():
                net_direction_total = v.get('net_direction_total')
                net_direction_total_amount = float(v.get('many_direction_total_amount')) - float(v.get('empty_direction_total_amount'))
                # side = '多仓' if net_direction_total_amount > 0 else '空仓'
                rate_net = float(rate.get(k, 0))
                net_direction_total_amount_u = net_direction_total_amount * rate_net
                # face = float(net_direction_total_amount) / float(net_direction_total) if float(net_direction_total) else 1
                net_position[k] = {'symbol': k,
                                   'net_total': net_direction_total,
                                   'net_total_amount': net_direction_total_amount,
                                   'net_total_amount_u': net_direction_total_amount_u,
                                   'many_direction_total_amount': float(v.get('many_direction_total_amount')),
                                   'empty_direction_total_amount': float(v.get('empty_direction_total_amount')),
                                   'rate': rate_net,
                                   # 'net_side': side,
                                   # 'face': face,
                                   'position_type': position_type,
                                   }
                if float(net_direction_total):
                    net_position[k]['face'] = float(net_direction_total_amount) / float(net_direction_total)
        return net_position

    net_position_full = await position(rate, is_full=1, position_type='全仓')
    net_position = await position(rate, is_full=0, position_type='逐仓')

    net_position_user = {}
    for s in net_position_full.keys() | net_position.keys():
        net_position_user[s] = {'symbol': s,
                                'net_total': (net_position.get(s, {}).get('net_total', 0) + net_position_full.get(s, {}).get('net_total', 0)),
                                'net_total_amount': (net_position.get(s, {}).get('net_total_amount', 0) + net_position_full.get(s, {}).get('net_total_amount', 0)),
                                'net_total_amount_u': (net_position.get(s, {}).get('net_total_amount_u', 0) + net_position_full.get(s, {}).get('net_total_amount_u', 0)),
                                'many_direction_total_amount': (net_position.get(s, {}).get('many_direction_total_amount', 0) + net_position_full.get(s, {}).get('many_direction_total_amount', 0)),
                                'empty_direction_total_amount': (net_position.get(s, {}).get('empty_direction_total_amount', 0) + net_position_full.get(s, {}).get('empty_direction_total_amount', 0)),
                                'rate': float(rate.get(s, 0)),
                                'face': max(net_position.get(s, {}).get('face', 0), net_position_full.get(s, {}).get('face', 0))
                                }
        net_position_user[s]['net_side'] = '多仓' if net_position_user[s]['net_total'] > 0 else '空仓'

    return net_position_user


async def get_data(res, userid_futurefee, net_position_user, position_type):
    acc_id_contract_not = acc_id_contract + userid_futurefee
    for i in res:
        user_id = i['user_id']
        if str(user_id) not in acc_id_contract_not:
            symbol = i['symbol']
            position_type = "全仓" if i['is_full'] == 2 else "逐仓"
            side = "多仓" if i['openDirection'] == 1 else "空仓"
            face_value = FACE_VALUE.get(symbol, 0)
            coef = 1 if side == "多仓" else -1
            net_t = float(i.get('amount', 0)) * coef
            direction_amount = net_t * face_value
            direction_amount_price = float(i.get('avgPrice', 0))

            # net_t = direction_amount / face_value if face_value else direction_amount
            # if not face_value:
            #     face_value = float(i.get('many_direction_amount', 0)) / float(i.get('many_direction', 0)) if float(i.get('many_direction', 0)) \
            #         else float(i.get('empty_direction_amount', 0)) / float(i.get('empty_direction', 0))
            d = [{'user_id': i['user_id'],
                  # 'side': '多仓' if direction_amount > 0 else '空仓',
                  'side': side,
                  'direction_amount': direction_amount,
                  'direction_amount_u': direction_amount * direction_amount_price,
                  'face_value': face_value,  # 有些接口返回值可能有错误，没有面值
                  # 'net_t': direction_amount / face_value if face_value else 0,
                  'net_t': net_t,  # 张数
                  'profit_loss': float(i['profitLoss']),
                  'risk_ratio': i['risk_ratio'],  # 风险率
                  'parity': i['parity'],  # 强平价格
                  'position_type': position_type
                  }]
            net_position_user[symbol] = d + net_position_user.get(symbol, [])
    return net_position_user


async def get_positon_user(symbol=None):
    page_size = 20
    res, res_full = [], []
    for page in range(1, 100):
        mm = await a_interfaces.contract_treaty_holdlist(page=page, page_size=page_size, symbol=symbol)
        res += mm['result']['data']['data']
        if float(mm['result']['data']['pager']['page_size']) <= page:
            break
    # for page in range(1, 100):
    #     mm = await a_interfaces.contract_treaty_fullholdlist(page=page, page_size=page_size, symbol=symbol)
    #     res_full += mm['result']['data']
    #     if len(mm['result']['data']) < page_size:
    #         break

    if res + res_full:
        userid_futurefee = [str(i) for i in (await a_interfaces.userid_futurefee())['result']]
        logger.info(f"{userid_futurefee=}")
        net_position_user = {}
        net_position_user = await get_data(res, userid_futurefee, net_position_user, position_type='逐仓')
        net_position_user = await get_data(res_full, userid_futurefee, net_position_user, position_type='全仓')
        return net_position_user
    return {}


async def get_positon_msg():
    net_position = await get_positon()
    net_position_user = await get_positon_user()
    # net_symbols = list(net_position.keys()) + list(net_position_user.keys())
    # net_s = set(net_position_symbols) - set(net_position_user_symbols)
    net_position_symbols_list = [v for k, v in net_position.items()]
    net_position_symbols_list = sorted(net_position_symbols_list, key=lambda net_position_symbols_list: abs(net_position_symbols_list['net_total_amount_u']), reverse=True)

    now_time = datetime.datetime.now()
    HOUR = now_time.hour
    MINUTE = now_time.minute
    cycle = {k: (HOUR + 1) % v for k, v in CAPITAL_RATE_PARAM.items() if (HOUR + 1) % v == 0}
    if cycle and MINUTE >= 30:
        fund_rate_all, error_symbol = await aapi.funding_rate_all(symbols=SYMBOLS_CONTRACT_PAIR)
        fund_rate_all = {s: v / 100 for s, v in fund_rate_all.items()}
    else:
        fund_rate_all = {}
    msg = ""
    for i in net_position_symbols_list:
        msg_a, msg_b = "", ""
        s = i['symbol']
        net_total_amount_u = i.get('net_total_amount_u', 0)
        net_position_user_s = net_position_user.get(s, [])
        num = len(net_position_user_s)
        profit_loss_all = sum([i['profit_loss'] for i in net_position_user_s]) if net_position_user_s else 0
        net_position_user_s_total = sum([i['net_t'] for i in net_position_user_s]) if net_position_user_s else 0
        net_position_user_s_amount_u = sum([i['direction_amount_u'] for i in net_position_user_s]) if net_position_user_s else 0
        net_position_user_s_total_side = '多' if net_position_user_s_total > 0 else '空'
        funding_rate = fund_rate_all.get(s, 0)
        if funding_rate or s in fund_rate_all.keys():
            s_funding_rate = f"资金费率:{round(funding_rate * 100, 3)}%"
            s_fund_user = f"资金费用:{int(-funding_rate * i['net_total_amount_u'])}U"
            s_fund_user1 = f"资金费用:{int(-funding_rate * net_position_user_s_amount_u)}U"
        else:
            s_funding_rate = ""
            s_fund_user = ""
            s_fund_user1 = ""

        if profit_loss_all or num > 0 or abs(net_total_amount_u) >= DIRECTION_AMOUNT_U:
            net_position_user_s_total_many = sum([i['net_t'] for i in net_position_user_s if i['net_t'] > 0]) if net_position_user_s else 0
            net_position_user_s_total_empty = -sum([i['net_t'] for i in net_position_user_s if i['net_t'] < 0]) if net_position_user_s else 0
            if net_position_user_s_total_many and net_position_user_s_total_empty:
                a = net_position_user_s_total_many / net_position_user_s_total_empty
                if a > 0:
                    coef = f"{round(a, 2)}:1"
                else:
                    coef = f"1:{round(a, 2)}"
            elif net_position_user_s_total_many:
                coef = f"{int(net_position_user_s_total_many)}:0"
            elif net_position_user_s_total_empty:
                coef = f"0:{int(net_position_user_s_total_empty)}"
            else:
                coef = "0:0"

            msg_a = f"【{s}】 {s_funding_rate}\n" \
                    f"         - 含交易员仓位:{int(i['net_total'])}张({i['net_side']} {int(i['net_total_amount_u'])}U) {s_fund_user}\n" \
                    f"         - {int(net_position_user_s_total)}张 ({net_position_user_s_total_side} {int(net_position_user_s_amount_u)}U) {num}人 浮:{int(profit_loss_all)}U {s_fund_user1} 多:空:{coef}\n"
            # f"         - {i['net_side']} {int(i['net_total'])}张 ({int(i['net_total_amount_u'])}U) 交易人数:{num} 总计浮盈:{int(profit_loss_all)}U\n"
            net_position_user_s = [i for i in net_position_user_s if abs(i['profit_loss']) > PROFIT_LOSS or abs(i['direction_amount_u']) >= DIRECTION_AMOUNT_U or -funding_rate * i['direction_amount_u'] > 1]
            if net_position_user_s:
                net_position_user_s = sorted(net_position_user_s, key=lambda net_position_user_s: abs(net_position_user_s['profit_loss']), reverse=True)
                for j in net_position_user_s:
                    direction_amount_u = int(j['direction_amount_u'])
                    profit_loss_b = j['profit_loss']
                    pay_funding = f"资金费用:{int(-funding_rate * direction_amount_u)}U" if funding_rate else ""
                    if direction_amount_u > DIRECTION_AMOUNT_U or abs(profit_loss_b) > PROFIT_LOSS or funding_rate:
                        msg_b += f"         ●  {j['user_id']} {int(j['net_t'])}张 ({j['side'].replace('仓', '')} {direction_amount_u}U) 浮:{int(profit_loss_b)}U {pay_funding}\n"
            if msg_b:
                msg += msg_a + msg_b
            elif abs(int(profit_loss_all)) > DIRECTION_AMOUNT_U or abs(i['net_total_amount_u']) > DIRECTION_AMOUNT_U or -funding_rate * i['net_total_amount_u'] > 50:
                msg += msg_a

    net_s = set(net_position_user.keys()) - set(net_position.keys())
    for s in net_s:
        net_position_user_s = net_position_user[s]
        num = len(net_position_user_s)
        profit_loss_all = sum([i['profit_loss'] for i in net_position_user_s]) if net_position_user_s else 0

        funding_rate = fund_rate_all.get(s, 0)
        s_funding_rate = f"资金费率:{round(funding_rate * 100, 3)}%" if funding_rate else ""
        net_position_user_s_total_many = sum([i['net_t'] for i in net_position_user_s if i['net_t'] > 0]) if net_position_user_s else 0
        net_position_user_s_total_empty = -sum([i['net_t'] for i in net_position_user_s if i['net_t'] < 0]) if net_position_user_s else 0
        if net_position_user_s_total_many and net_position_user_s_total_empty:
            a = net_position_user_s_total_many / net_position_user_s_total_empty
            if a > 0:
                coef = f"{round(a, 2)}:1"
            else:
                coef = f"1:{round(a, 2)}"
        elif net_position_user_s_total_many:
            coef = f"{int(net_position_user_s_total_many)}:0"
        elif net_position_user_s_total_empty:
            coef = f"0:{int(net_position_user_s_total_empty)}"
        else:
            coef = "0:0"

        if num >= NUM or abs(profit_loss_all) > PROFIT_LOSS_ALL or funding_rate:
            msg += f"【{s}】{s_funding_rate}\n" \
                   f"         - 交易人数:{num} 总计浮盈:{int(profit_loss_all)}U 多:空:{coef}\n"
            net_position_user_s = [i for i in net_position_user_s if abs(i['profit_loss']) > PROFIT_LOSS or abs(i['direction_amount_u']) >= DIRECTION_AMOUNT_U or -funding_rate * i['direction_amount_u'] > 1]
            if net_position_user_s:
                net_position_user_s = sorted(net_position_user_s, key=lambda net_position_user_s: abs(net_position_user_s['direction_amount_u']), reverse=True)
                for j in net_position_user_s:
                    direction_amount_u = int(j['direction_amount_u'])
                    pay_funding = f"资金费用:{int(-funding_rate * direction_amount_u)}U" if funding_rate else ""
                    msg += f"         ●  {j['user_id']} {int(j['net_t'])}张 ({j['side'].replace('仓', '')} {direction_amount_u}U) 浮:{int(j['profit_loss'])} {pay_funding}\n"
    mess_quant_web = ""
    if msg:
        msg = f"🎆\\#*合约用户持仓*🎆\n" \
              f"*交易人数超过:{NUM}人，总计盈亏超过:{PROFIT_LOSS_ALL}U*\n" \
              f"*浮盈浮亏超过:{PROFIT_LOSS}U 仓位超过:{DIRECTION_AMOUNT_U}U ({int(fetch_timeout / 60)}min/次)*\n" \
              f"资金费用:结算前20-30min(5min/次),结算前10min(2min/次)\n" \
              f"{msg}"
        sendmessage.send_telegram_msg_mdv2(msg, ser='contract_info_user')
        mess_quant_web = msg
    monitor.get_a_monitor(event_name='hy_hedge_position_diff', msg=mess_quant_web)


async def get_positon_all():
    start_time = 0
    while True:
        try:
            if time.time() - start_time >= 60 * 60 * 24:
                get_face_value()
            #await get_positon_msg()
            await heartbeat.i_live_well(server='合约用户持仓', frequency=fetch_timeout * 2.1, index=33)
            logger.info(f" contract_user_list wait 2min")
            # await asyncio.sleep(sleep_timeout)
        except:
            mm = traceback.format_exc()
            sendmessage.send_telegram_msg(f'合约用户持仓监控\n{mm}', ser='Alarm')
            logger.error(f" error:合约用户持仓")
            # await asyncio.sleep(sleep_timeout / 2)
        finally:
            ts = await sleep_time(PARAM=CAPITAL_RATE_PARAM, fetch_timeout=fetch_timeout)
            # sendmessage.send_telegram_msg(f'合约用户持仓监控\n休息时间:{ts}s', ser='Alarm')
            await asyncio.sleep(max(ts, 60 * 2))


async def contract_run():
    task = [
        get_positon_all(),
        get_capital_rate_param()
    ]
    await asyncio.gather(*task)


async def test():
    get_face_value()
    await get_positon_msg()


if __name__ == "__main__":
    asyncio.run(contract_run())
