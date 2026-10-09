import ujson
import time, datetime, json

import asyncio
import traceback
import sys, os

file = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(file)

from libs.requestSession import G_RequestSession
from config.infor_contract import SYMBOLS_CONTRACT_PAIR
from libs import heartbeat, sendmessage
from config import infor_load, monitor
from exchange.restful_api.abc_contract import AApi
from contract.con_position_user_list import get_positon, get_positon_user
from contract.contract_setting import capitalrateparam, sleep_time, CAPITAL_RATE_PARAM, get_capital_rate_param

path = sys.path[0]
filename = f'{path}/contract_exchange_symbols.json'

a_interfaces = AApi()
headers = {
    'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

contract_symbols = sorted(SYMBOLS_CONTRACT_PAIR)
FUNDING_RATE_EXCHANGES = {}
ROUND = 4
fetch_timeout = 60 * 30
POSITION_U = 10 * 10000
PAYMENT = 20
RATE_FUNDING_COEF_DIFF_DIRECTION = 0.003
RATE_FUNDING_COEF_SAME_DIRECTION = 0.0025
RATE_FUNDING_COEF_ONESELF = 0.0033
RATE_FUNDING_COEF_EX = 0.003
sectionA_B = 0.01
# FOLLOW_EXCHANGE_ORDER_REVERSE = {'bn', 'hb', 'okex', 'bitget'}
ERROR_EX = []


class BinanceApi:
    ex = "bn"

    async def funding_rate(self):
        try:
            bn_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
            spec_contract_symbol = {k: v[0] for k, v in infor_load.spec_contract_symbol_rate_mapping.get(self.ex, {}).items() if v}
            symbols = contract_symbols + list(spec_contract_symbol.keys())
            async with G_RequestSession.request.get(bn_url, headers=headers) as r:
                res = await r.text()
                res = ujson.loads(res)
                usdt_busd_zone_list = {}
                for r in res:
                    s = r["symbol"].replace("USDT", "-USDT")
                    if s in symbols:
                        f = r["lastFundingRate"]
                        usdt_busd_zone_list[spec_contract_symbol.get(s, s)] = round(float(f) * 100, ROUND)
                FUNDING_RATE_EXCHANGES[self.ex] = usdt_busd_zone_list
        except:
            ERROR_EX.append(self.ex)


class HuobiApi:
    ex = "hb"

    async def funding_rate(self):
        try:
            hb_url = "https://api.hbdm.com/linear-swap-api/v1/swap_batch_funding_rate"
            spec_contract_symbol = {k: v[0] for k, v in infor_load.spec_contract_symbol_rate_mapping.get(self.ex, {}).items() if v}
            symbols = contract_symbols + list(spec_contract_symbol.keys())
            async with G_RequestSession.request.get(hb_url, headers=headers) as r:
                res = await r.text()
                res = ujson.loads(res)
                usdt_busd_zone_list = {}
                for r in res['data']:
                    s = r["contract_code"]
                    f = r["funding_rate"]
                    if s in symbols:
                        usdt_busd_zone_list[spec_contract_symbol.get(s, s)] = round(float(f) * 100, ROUND)
                FUNDING_RATE_EXCHANGES[self.ex] = usdt_busd_zone_list
        except:
            ERROR_EX.append(self.ex)


class GateioApi:
    ex = "gate"

    async def funding_rate(self):
        try:
            gate_url = "https://api.gateio.ws/api/v4/futures/usdt/tickers"
            spec_contract_symbol = {k: v[0] for k, v in infor_load.spec_contract_symbol_rate_mapping.get(self.ex, {}).items() if v}
            symbols = contract_symbols + list(spec_contract_symbol.keys())
            async with G_RequestSession.request.get(gate_url, headers=headers) as r:
                res = await r.text()
                res = ujson.loads(res)
                usdt_busd_zone_list = {}
                for r in res:
                    s = r["contract"].replace('_', '-')
                    f = r["funding_rate"]
                    if s in symbols:
                        usdt_busd_zone_list[spec_contract_symbol.get(s, s)] = round(float(f) * 100, ROUND)
                FUNDING_RATE_EXCHANGES[self.ex] = usdt_busd_zone_list
        except:
            ERROR_EX.append(self.ex)


class OkexApi:
    ex = "okex"

    async def funding_rate(self):
        error = []
        try:
            usdt_busd_zone_list = {}
            # tasks = [asyncio.create_task(self.fund_rate(symbol, usdt_busd_zone_list)) for symbol in contract_symbols]
            # await asyncio.wait(tasks)
            spec_contract_symbol = {k: v[0] for k, v in infor_load.spec_contract_symbol_rate_mapping.get(self.ex, {}).items() if v}
            symbols = contract_symbols + list(spec_contract_symbol.keys())
            for symbol in symbols:
                s = await self.fund_rate(symbol, usdt_busd_zone_list, spec_contract_symbol)
                if s:
                    error.append(s)
                await asyncio.sleep(0.2)

            FUNDING_RATE_EXCHANGES[self.ex] = usdt_busd_zone_list
        except:
            if error:
                ERROR_EX.append(f"{self.ex}:{error}")

    async def fund_rate(self, symbol, usdt_busd_zone_list, spec_contract_symbol):
        url = f"https://www.okx.com/api/v5/public/funding-rate?instId={symbol}-SWAP"
        try:
            async with G_RequestSession.request.get(url, headers=headers) as r:
                res = await r.text()
                res = ujson.loads(res)
                if res['code'] == '0':
                    f = res['data'][0]["fundingRate"]
                    usdt_busd_zone_list[spec_contract_symbol.get(symbol, symbol)] = round(float(f) * 100, ROUND)
        except:
            print('error', self.ex, symbol)
            return symbol


class AbcApi:
    ex = "abc"

    async def funding_rate(self):
        usdt_busd_zone_list, error = await AApi().funding_rate_all(symbols=contract_symbols)
        FUNDING_RATE_EXCHANGES[self.ex] = usdt_busd_zone_list
        if error:
            ERROR_EX.append(f'{self.ex}:{error}')


#
# async def get_positon():
#     net_user_total = {}
#     res = await a_interfaces.contract_position(symbol=None, self_user=1)
#     res = res.get('result', {}).get('data', {})
#     for k, v in res.items():
#         net_direction_total = v.get('net_direction_total')
#         net_direction_total_amount = float(v.get('many_direction_total_amount')) + float(v.get('empty_direction_total_amount'))
#         side = '多仓' if net_direction_total_amount > 0 else '空仓'
#         net_user_total[k] = net_direction_total
#     return net_user_total

async def get_exchange_symbols():
    try:
        exchange_symbols = json.load(open(filename))
        spec_contract_symbol_rate_map = infor_load.libs_config.SPEC_CONTRACT_SYMBOL_RATE_MAPPING
        exchange_symbols = {ex: list(v.keys()) + list(spec_contract_symbol_rate_map.get(ex, {}).keys()) for ex, v in exchange_symbols.items() if isinstance(v, dict)}
    except:
        exchange_symbols = {}
    return exchange_symbols


async def capital_rate():
    exchanges = {
        'abc': AbcApi(),
        'bn': BinanceApi(),
        'okex': OkexApi(),
        'gate': GateioApi(),
        # 'hb': HuobiApi(),
    }
    while True:
        now_time = datetime.datetime.now()
        HOUR = now_time.hour
        MINUTE = now_time.minute
        cycle = {k: (HOUR + 1) % v for k, v in CAPITAL_RATE_PARAM.items() if (HOUR + 1) % v == 0}
        exchange_symbols = await get_exchange_symbols()
        try:
            tasks = [asyncio.create_task(exapi.funding_rate()) for ex, exapi in exchanges.items()]
            await asyncio.wait(tasks)
            # message = f"外部交易所当前资金费率 {int(fetch_timeout / 60)}min/次\n"
            message1, message2, message3, message_net, message, message_ex = [], [], [], "", "", ""
            message4, message5 = "", ""
            mess_quant_web = ""
            abc = {}
            for symbol in contract_symbols:
                other = {}
                for ex in exchanges:
                    if ex in ['abc']:
                        abc[symbol] = FUNDING_RATE_EXCHANGES[ex][symbol]
                    elif FUNDING_RATE_EXCHANGES[ex].get(symbol) and (symbol in exchange_symbols.get(ex) or not exchange_symbols):
                        other[ex] = FUNDING_RATE_EXCHANGES[ex][symbol]

                # 1 如果方向跟外部都不一样， 并且abs(abc-min(bn, ok,...)) > 0.0005 或者
                # 2 abs(abc)大于同方向所有都超过0.0005
                if abc.get(symbol, "") and other:
                    positive = all(x > 0 for x in other.values())  # 判断是否所有元素都大于零
                    negative = all(x < 0 for x in other.values())
                    abc_position = abc[symbol]
                    other_msg = "  ".join([f"*{k}*:{'{:.4f}'.format(v)}%" for k, v in other.items()])
                    msg = f"【{symbol}】:{abc[symbol]}%\n          {other_msg}\n"
                    if (abc_position > 0 and negative) or (abc_position < 0 and positive):
                        if abs(abc_position - min(other.values())) > RATE_FUNDING_COEF_DIFF_DIRECTION * 100:
                            message1.append(msg)
                    else:
                        other_position = max(abs(x) for x in other.values() if x * abc_position > 0)
                        if abs(abc_position) - other_position > RATE_FUNDING_COEF_SAME_DIRECTION * 100:
                            message2.append(msg)
                    if abs(abc_position) >= RATE_FUNDING_COEF_ONESELF * 100 and msg not in message2:
                        message2.append(msg)

                    other_max = max([abs(v) for ex, v in other.items()])
                    if other_max >= RATE_FUNDING_COEF_EX * 100:
                        message3.append(msg)

            param_interest = await capitalrateparam()
            interest = []
            for i in param_interest:
                if i['interest'] != '0' or min(abs(float(i['sectionA'])), abs(float(i['sectionB']))) < sectionA_B:
                    inst = f"{float(i['interest'])}"
                    if min(abs(float(i['sectionA'])), abs(float(i['sectionB']))) < sectionA_B:
                        section_ab = f"sectionA:{i['sectionA']},sectionB:{i['sectionB']}"
                    else:
                        section_ab = ""
                    f = f"({round(abc.get(i['name'], 0), 4)}%)"
                    interest.append([i['name'], inst, section_ab, f])
            if interest:
                interest = sorted(interest, key=lambda x: x[1], reverse=True)
                # interest = sorted(interest.items(), key=lambda x: abs(x[1]), reverse=True)
                cycle2 = {k: (HOUR + 2) % v for k, v in CAPITAL_RATE_PARAM.items() if (HOUR + 2) % v == 0}
                if cycle or cycle2:
                    message5 = "\n".join([f"{i[0]}  {i[1]}  {i[2]} {i[3]}" for i in interest])

            if cycle and MINUTE >= 30:
                net_user_total = await get_positon()
                for k, v in net_user_total.items():
                    net_total = v['net_total']
                    direction_amount = v['net_total_amount']
                    direction_amount_u = v['net_total_amount_u']
                    payment = direction_amount_u * float(abc.get(k, 0)) / 100

                    if net_total * abc.get(k, 0) < 0 and abs(payment) >= PAYMENT:
                        message_net += f"【{k}】 \n" \
                                       f"          用户持仓:{net_total}张({int(direction_amount_u)}U) 资金费率{abc[k]}% 收取:{-int(payment)}U\n"

                # try:
                #     positon_user = {}
                #     if len(cycle) < len(contract_symbols):
                #         for s in cycle:
                #             positon_user.update(await get_positon_user(symbol=s))
                #     else:
                #         positon_user = await get_positon_user()
                #     for k, net_position_user_s in positon_user.items():
                #         payment = 0
                #         msg_a = f"【{k}】资金费率{abc[k]}% \n"
                #
                #         if not net_user_total.get(k):
                #             msg_a += f"         - 含交易员仓位:- \n"
                #         else:
                #             net_side = '多仓' if net_user_total.get(k).get('net_total_amount') > 0 else "空仓"
                #             payment = -net_user_total[k].get('net_total_amount_u', 0) * float(abc[k]) / 100
                #             msg_a += f"         - 含交易员仓位:{net_side} {int(net_user_total.get(k).get('net_total_amount'))}张 ({int(net_user_total.get(k).get('net_total_amount_u'))}U)  资金费用:{int(payment)}U\n"
                #         profit_loss_all = sum([i['profit_loss'] for i in net_position_user_s]) if net_position_user_s else 0
                #         net_position_user_s_total = sum([i['net_t'] for i in net_position_user_s]) if net_position_user_s else 0
                #         net_position_user_s_amount_u = sum([i['direction_amount_u'] for i in net_position_user_s]) if net_position_user_s else 0
                #         net_position_user_s_total_side = '多仓' if net_position_user_s_total > 0 else '空仓'
                #         payment_user = - net_position_user_s_amount_u * float(abc[k]) / 100
                #         msg_a += f"         - {net_position_user_s_total_side} {int(net_position_user_s_total)}张 ({int(net_position_user_s_amount_u)}U) 资金费用:{int(payment_user)}U\n"
                #         net_position_user_s = sorted(net_position_user_s, key=lambda net_position_user_s: net_position_user_s['direction_amount_u'], reverse=True)
                #         for j in net_position_user_s:
                #             direction_amount_u = j['direction_amount_u']
                #             payment_a = -direction_amount_u * float(abc[k]) / 100
                #             if abs(payment_a) > 1:
                #                 msg_a += f"         ●  id:{j['user_id']} {j['side']} {int(j['net_t'])}张 ({int(direction_amount_u)}U) 资金费用:{int(payment_a)}U\n"
                #         if int(payment) > 0 or int(payment_user) > 0:
                #             message4 += msg_a
                # except:
                #     message4 += "获取用户详细仓位异常\n"
            if HOUR % 8 > 0:
                if message1:
                    message1 = ''.join(message1)
                    message += f"*方向跟外部都不一样,并且abs(abc-min(bn, ok,...)) > {RATE_FUNDING_COEF_DIFF_DIRECTION} ({int(fetch_timeout / 60)}min/次)*\n{message1}\n"
                if message2:
                    message2 = ''.join(message2)
                    message += f"*abs(abc)大于同方向所有都 > {RATE_FUNDING_COEF_SAME_DIRECTION} or abs(abc)>{RATE_FUNDING_COEF_ONESELF} ({int(fetch_timeout / 60)}min/次)*\n{message2}\n"
                if message3:
                    message3 = ''.join(message3)
                    message += f"*abs(外部交易所) > {RATE_FUNDING_COEF_EX} ({int(fetch_timeout / 60)}min/次)*\n{message3}\n"
            if message_net:
                message += f"*结算前最后一小时,`abc仓位与资金费率不一致,并且用户收取>{PAYMENT}U`，需要调整 {int(fetch_timeout / 60)}min/次*\n{message_net}"
            if message4:
                message += f"*结算前最后10min,用户持仓, 1min/次*\n{message4}"
            if message5:
                message += f"*合约参数 interest不等于0 or min(abs(sectionA),abs(sectionB))<{int(sectionA_B * 100)}%*\n{message5}"

            if message:
                #sendmessage.send_telegram_msg_mdv2(message, ser='fund_rate')
                mess_quant_web = message
            monitor.get_a_monitor(event_name='hy_funding_rate', msg=mess_quant_web)
            await heartbeat.i_live_well(server='合约资金费率', frequency=60 * 60 * 2.1, index=35)
            print('ok')
        except:
            mm = traceback.format_exc()
            sendmessage.send_telegram_msg(f'con_capitalrate.py\n{mm}', ser='Alarm')
        finally:
            ts = await sleep_time(PARAM=CAPITAL_RATE_PARAM, fetch_timeout=fetch_timeout)
            await asyncio.sleep(max(ts, 60 * 2))


async def contract_run():
    task = [
        capital_rate(),
        get_capital_rate_param()
    ]
    await asyncio.gather(*task)


if __name__ == "__main__":
    asyncio.run(contract_run())
