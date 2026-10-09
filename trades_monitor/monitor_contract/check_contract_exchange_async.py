import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.send_tglegram_msg import send_telegram_async
import asyncio
from scaffold.mysql import G_MysqlSession


async def get_status_exchange():
    datas = []
    sql = f''' select * from exchange_symbols_contract_referrence'''
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
    datas = await get_status_exchange()
    msg = '！！当前合约交易对可添加参考交易所, 值班人员核对后通知相关人员调整对标:\n'
    for data in datas:
        symbol = data['symbol']
        exchange = eval(data['contract_exchange'])
        spot_exchange = eval(data['exchange'])
        exchange_other = data['exchange_other']
        market = data['market']
        change_list, li = [], []
        if "okex" in exchange and 'bn' in exchange:
            continue
        else:
            for ex in ['bn', 'okex']:
                if ex in eval(exchange_other):
                    if ex not in exchange:
                        change_list.append(ex)
            if len(change_list) == 0:
                continue
            for ex in ['gate', 'mxc', 'bitget']:
                if ex in eval(exchange_other):
                    if ex not in exchange:
                        change_list.append(ex)
        for i in eval(market):
            for ex in change_list:
                base_list = i.get(ex, [])
                base_list = [b.split('-')[-1] for b in base_list]
                if 'USDT' in base_list:
                    li.append(ex)
        if len(li) == len(change_list) and len(change_list) != 0:
            results = list(set(exchange)) + change_list
            msg += f'【{symbol}】合约对标{str(exchange)} ==> {str(results)}, 当前现货对标 {spot_exchange}\n'
    print(msg)
    if msg != '！！当前合约交易对可添加参考交易所, 值班人员核对后通知相关人员调整对标:\n':
        await send_telegram_async(msg, 'warning')


async def main():
    await exchange_refer()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
