import json
import os, sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.send_tglegram_msg import send_telegram_async
from scaffold.mysql import G_MysqlSession
import asyncio
from libs import heartbeat
from many_configs import global_variable
from many_configs.initializer import init_exchange_share_memory
import hashlib


async def get_status(currency=None):
    datas = []
    if currency:
        sql = f''' select * from withdraw_deposit where currency="{currency}"'''
    else:
        sql = f''' select * from withdraw_deposit'''
    result, col_list = await G_MysqlSession.fetch_all_and_description(sql)
    col = []
    for i in col_list:
        col.append(i[0])
    for re in result:
        acc = col
        re = dict(zip(acc, list(re)))
        for k, v in re.items():
            if v == None:
                re[k] = '_'
            if v == 0:
                re[k] = '_'
        datas.append(re)
    return datas


# 充提状态异常(相同链Websea和对冲交易所不一致）
async def monitor_websea_chain():
    await heartbeat.i_live_well("链状态与对冲交易所一致性", 60 * 17, 66)
    hedge_exchange = ['bn', 'gate', 'hb', 'okex', "mxc", 'bitget']
    dicts = {'bn': 'binance', 'hb': 'huobi', 'gate': "gateio", 'okex': 'okex', 'mxc': 'mexc', 'bitget': 'bitget'}
    datas = await get_status()
    msg = '！！！紧急，充提状态异常(相同链Websea与对冲交易所不一致，反馈相关人员注意监控):\n'
    res = []
    for i in datas:
        websea_hedge = eval(i.get('websea_hedge'))
        for hedge in websea_hedge:
            if hedge in hedge_exchange:
                res.append(i)
                continue
    curreny_list = []
    print(res)
    for i in res:
        websea_status = eval(i['websea'])
        websea_hedge = eval(i.get('websea_hedge'))
        for re in websea_status:
            for hedge in websea_hedge:
                msg_currency = ''
                if i[dicts.get(hedge)] == '无当前币种':
                    continue
                print(f"---{dicts.get(hedge)=}")
                print(f"--{i[dicts.get(hedge)]=}")
                print(f"--{i=}")
                hedge_status = eval(i[dicts.get(hedge)])
                hedge_chain = [chain.split('|')[0] for chain in hedge_status if chain != '无当前币种']
                if (re not in hedge_status) and (not (re.split('|')[0] not in hedge_chain and re.split('|')[1] in ['暂停充提'])) and (hedge in hedge_exchange):
                    msg_currency = f''' {i["currency"]}  对冲交易所: {i["websea_hedge"]}\n 火币: {i["huobi"]}\n 币安: {i["binance"]}\n okex: {i["okex"]}\n gateio: {i["gateio"]}\n mexc: {i["mexc"]}\n bitget: {i["bitget"]}\n websea: {i["websea"]}\n\n'''
                if i['currency'] not in curreny_list and msg_currency:
                    curreny_list.append(i['currency'])
                    msg += msg_currency
    print(msg)
    exchange_msg_dict = global_variable.SHARE_EXCHANGE.get('exchange', json.dumps({}))
    exchange_msg_dict = json.loads(exchange_msg_dict)
    print('SHARE_EXCHANGE ', exchange_msg_dict)
    if msg != '！！！紧急，充提状态异常(相同链Websea与对冲交易所不一致，反馈相关人员注意监控):\n':
        msg_md5 = hashlib.md5(msg.encode(encoding='UTF-8')).hexdigest()
        print('msg md5', msg_md5)
        msg_time = exchange_msg_dict.get(msg_md5, int(time.time()))
        current_time = int(time.time())
        already_msg = []
        # 超过一小时发送一次
        if current_time - int(msg_time) >= 8 * 60 * 60:
            msg_li = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
            for send_msg in msg_li:
                await send_telegram_async(send_msg, 'warning')
            exchange_msg_dict[msg_md5] = current_time
            already_msg = msg_li
        # 如果缓存中没有或者新的一条跟上一条不一样就发送
        if not exchange_msg_dict or (exchange_msg_dict and msg_md5 != list(exchange_msg_dict.keys())[-1]):
            msg_li = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
            for send_msg in msg_li:
                if msg_li not in already_msg:
                    await send_telegram_async(send_msg, 'warning')
            if exchange_msg_dict.get(msg_md5):
                del exchange_msg_dict[msg_md5]
            exchange_msg_dict[msg_md5] = current_time
    # 缓存中只保留最新的10条msg
    print('exchange_msg_dict', exchange_msg_dict)
    keep_key = list(exchange_msg_dict.keys())[-10:]
    keep_exchange_msg_dict = {}
    for key in keep_key:
        keep_exchange_msg_dict[key] = exchange_msg_dict[key]
    global_variable.SHARE_EXCHANGE['exchange'] = json.dumps(keep_exchange_msg_dict)
    print('SHARE_EXCHANGE result ', global_variable.SHARE_EXCHANGE)
    await heartbeat.i_live_well("链状态与对冲交易所一致性", 60 * 17, 66)


async def main():
    init_exchange_share_memory()
    await monitor_websea_chain()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
