import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.send_tglegram_msg import send_telegram_async
import asyncio
from scaffold.mysql import G_MysqlSession


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
        if currency:
            datas = re
        else:
            datas.append(re)
    return datas


async def get_status_exchange():
    datas = []
    sql = f''' select * from exchange_symbols_referrence'''
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


# 当前币种可添加参考交易所
async def exchange_refer():
    exchange_dict = {'hb': 'huobi', 'okex': 'okex', "gate": 'gateio', 'bn': 'binance', 'mexc': 'mxc',
                     'bitget': 'bitget'}
    datas = await get_status_exchange()
    msg = '！！当前币种可添加参考交易所, 值班人员核对后通知相关人员调整对标:\n'
    for data in datas:
        currency = data['currency']
        exchange = eval(data['exchange'])
        exchange_other = data['exchange_other']
        market = data['market']
        change_list, li = [], []
        if 'bn' in exchange and ("okex" in exchange or 'gate' in exchange):
            continue
        else:
            for ex in ['bn']:
                if ex in eval(exchange_other):
                    if ex not in exchange:
                        change_list.append(ex)
            if len(change_list) == 0:
                continue
            for ex in ['okex', 'gate', 'mxc', 'bitget']:
                if ex in eval(exchange_other):
                    if ex not in exchange:
                        change_list.append(ex)
        for i in eval(market):
            for ex in change_list:
                if ex == 'bn':
                    for j in i.get(ex, []):
                        if 'USDT' in j:
                            li.append(ex)
                            break
                elif 'USDT' in i.get(ex, []):
                    li.append(ex)
        li = list(set(li))
        if len(li) == len(change_list) and len(change_list) != 0:
            withdraw = await get_status(currency)
            re_list = []
            for i in change_list:
                ex = exchange_dict[i]
                if '正常' in withdraw[ex]:
                    re_list.append(i)
            if len(re_list) != 0 and len(change_list) != 0:
                results = list(set(exchange)) + re_list
                if 'bn' in re_list or 'okex' in re_list:
                    msg += f'【{currency}】对标{str(exchange)} ==> {str(results)}\n'
    print(msg)
    if msg != '！！当前币种可添加参考交易所, 值班人员核对后通知相关人员调整对标:\n':
        msg_li = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for send_msg in msg_li:
            await send_telegram_async(send_msg, 'warning')


# 单个对标交易所关闭充|提, Websea正常，请查看价差情况，是否需要切换参考
async def pair_monitor():
    exchange_dict = {'hb': 'huobi', 'okex': 'okex', "gate": 'gateio', 'bn': 'binance', "mxc": 'mexc'}
    datas = await get_status_exchange()
    msg = '单个对标交易所关闭充|提, Websea正常，请查看价差情况，是否需要切换参考:\n'
    for data in datas:
        currency = data['currency']
        exchange = eval(data['exchange'])
        withdraw = await get_status(currency)
        re_list = []
        re_dict = {}
        for i in exchange:
            if i not in ['pancake', 'uniswap', 'sushi', 'mdex', 'matic', 'websea']:
                ex = exchange_dict[i]
                try:
                    if '正常' in str(withdraw[ex]):
                        re_list.append(i)
                    else:
                        re_dict[ex] = withdraw[ex]
                except:
                    pass
        if len(re_list) != len(exchange) and len(re_list) != 0 and re_dict and currency != 'FIL6':
            if '正常' in withdraw['websea']:
                msg += f"【{currency}】 对标交易所{str(exchange)}  充提状态{re_dict}\n"
    print(msg)
    if msg != '单个对标交易所关闭充|提, Websea正常，请查看价差情况，是否需要切换参考:\n':
        await send_telegram_async(msg, 'warning')


async def main():
    await exchange_refer()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
