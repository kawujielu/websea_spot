#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy

import urllib3
import pandas as pd
import time, datetime
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmysql import G_MysqlSession
from libs import heartbeat, sendmessage
from exchange.restful_api.abc_contract import AApi
from config import monitor, infor, infor_load, infor_contract, infor_start_amount

# 监控哪些账户
acc_contract_list = infor_contract.contract_account
SYMBOLS_PAIR = infor_contract.SYMBOLS_CONTRACT_PAIR


def sub_total(df_account):
    df_all = df_account.groupby(['symbol'])['avail', 'now_amount', 'start_amount'].sum().reset_index()
    df_all['总数占比'] = df_all['now_amount'] / df_all['start_amount']
    df_all['可用占比'] = df_all['avail'] / df_all['now_amount']
    df_all = df_all[['symbol', 'now_amount', 'avail', 'start_amount', '可用占比', '总数占比']]
    return df_all


def DataTotuple(data):
    """
    create table acc_sub(
    `index` int not null auto_increment,
    time datetime default current_timestamp on update current_timestamp,
    account_name varchar(10),
    avail double,
    symbol varchar(15),
    frozen double,
    hold double,
    now_amount double,
    start_amount double ,
    now_start_pro float(4,2),
    primary key (`index` , time ,symbol)
    );

    create table acc_total(
    `index` int not null auto_increment,
    time datetime default current_timestamp on update current_timestamp,
    symbol varchar(15),
    amount_all double,
    avail double,
    start_amount double,
    可用占比 double(4,2),
    总数占比 double(4,2),
    primary key (`index` , time ,symbol)
    );
    """
    valuse = ''
    for re in data.values:
        valuse += f'{tuple(re)},'
    valuse = valuse[:-1]
    valuse = valuse.replace('nan', 'NULL')
    return valuse


async def get_wallet(apikey, start_amount_dict, account_name, symbol_list, id):
    ao = AApi(token=apikey['token'], secret_key=apikey['sk'])
    res = await ao.wallet_contract()
    d = []
    if res['errno'] in [20529, 20522]:
        mess = f'【error】:ID：{id}：{res}'
        sendmessage.send_telegram_msg(message=mess, ser='EmerWarning')
    market_wallets = res["result"]
    for market_wallet in market_wallets:
        if market_wallet['symbol'] in symbol_list:
            market_wallet["start_amount"] = start_amount_dict.get(market_wallet['symbol'], 0)
            market_wallet["account_name"] = account_name
            market_wallet['now_amount'] = float(market_wallet['avail']) + float(market_wallet['frozen'])
            d.append(market_wallet)
    return d


# 获取1账户数目
async def Amount(symbol_list, accountList, start_amount):
    tasks = []
    res = []
    for k in accountList:
        account_name = k
        v = acc_contract_list[k]
        apikey = v['apikey']
        id = v.get('id', {})
        start_amount_dict = start_amount.get(str(id), {})
        tasks.append(asyncio.create_task(get_wallet(apikey, start_amount_dict, account_name, symbol_list, id)))
    for t in tasks:
        res += (await t)
    df_account_all = pd.DataFrame(res)
    return df_account_all


# 读取配置参考值数据
async def read_con_mysql():
    sql = 'select * from reference_fund_contract;'
    results, title = await G_MysqlSession.fetch_all(sql)
    temp = pd.DataFrame(list(results), columns=title)
    return temp


# 当前资金少于初始资金
async def get_acc_amount_pro(now):
    mess_quant_web = ''
    START_AMOUNT_SPOT, START_AMOUNT_CONTRACT = await infor_start_amount.get_start_amount()
    df_account_all = await Amount(symbol_list=SYMBOLS_PAIR, accountList=acc_contract_list, start_amount=START_AMOUNT_CONTRACT)
    df_reference_fund = await read_con_mysql()
    df = pd.merge(df_account_all, df_reference_fund, on=['account_name', 'symbol'], how='left')
    df = df[['account_name', 'symbol', 'frozen', 'now_amount', 'start_amount', 'reference_amount']]

    df['now_amount'] = df['now_amount'].astype(float)
    df['reference_amount'] = df['reference_amount'].astype(float)

    df = df[df['reference_amount'] != 0]
    df['pro'] = df['now_amount'] / df['reference_amount']
    df = df[df['pro'] <= 0.2]
    dff = copy.deepcopy(df)
    print(df[['account_name', 'symbol', 'pro']])
    if not df.empty:
        mes = f'{now}\n【合约】' + f"当前资金少于初始资金的20%,需要划转\n"
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            acc = df['account_name'].iloc[i]
            purpose = acc_contract_list[acc]['purpose']
            id = acc_contract_list[acc]['id']
            now_amount = int(df['now_amount'].iloc[i])
            reference_amount = (df['reference_amount'].iloc[i]).astype(int)
            proportion = (df['pro'].iloc[i] * 100).__round__(2)
            mes += f"【{symbol}】\n" \
                   f"账户:{acc} - {id} - {purpose}\n" \
                   f"当前数量:{now_amount}\n" \
                   f"参考数量:{reference_amount}\n" \
                   f"数量占比:{proportion}%\n\n"
            mess_quant_web += f"<b style='color:#FF0000'>【{symbol}】 {acc}</b> 当前数量:{now_amount} 初始数量:{reference_amount} 占比:{proportion}%<br>"
        sendmessage.send_telegram_msg(message=mes, ser='spot_info')
        print(f'{now} Acc_amount_pro | 正常')
    monitor.get_a_monitor(event_name='hy_transfer', msg=mess_quant_web)

    # 初始值/当前参考值 < 0.2 报警
    dff['start_amount'] = dff['start_amount'].astype(float)

    dff['pro'] = dff['now_amount'] / dff['start_amount']
    dff = dff[(dff['pro'] <= 0.2) | (dff['start_amount'] <= 0)]
    if not dff.empty:
        msg = f"【合约】当前资金少于初始资金的20%,需要划转\n"
        for i in range(len(dff)):
            symbol = dff['symbol'].iloc[i]
            acc = dff['account_name'].iloc[i]
            now_amount = int(dff['now_amount'].iloc[i])
            start_amount = (dff['start_amount'].iloc[i]).astype(int)
            proportion = (dff['pro'].iloc[i] * 100).__round__(2)
            id = acc_contract_list[acc]['id']
            purpose = acc_contract_list[acc]['purpose']
            msg += f"【{symbol}】\n" \
                   f"账户:{acc}-{id}-{purpose}\n" \
                   f"当前数量:{now_amount}\n" \
                   f"初始数量:{start_amount}\n" \
                   f"数量占比:{proportion}%\n\n"
        sendmessage.send_telegram_msg(message=msg, ser='spot_info')

async def contract_run():
    try:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await get_acc_amount_pro(now)
        await heartbeat.i_live_well(server='合约数量监控', frequency=60 * 30, index=31)
    except Exception as e:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sendmessage.send_telegram_msg(message=f'{now} | error：contract Acc_amount {e}', ser='Alarm')
        print(f'{now} | error :contract acc_amount -->> {e}')


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
