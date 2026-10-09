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
from exchange.restful_api.abc_spot import AApi
from config import infor, monitor, infor_start_amount

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 不提示警告
pd.set_option('mode.chained_assignment', None)

SYMBOLS_LIST = infor.SYMBOLS_LIST

# 监控数量账户
spot_account_list = infor.spot_account
account_list = list(spot_account_list.keys())[:17]


def sub_total(df_account):
    df_all = df_account.groupby(['currency'])['available', 'now_amount', 'start_amount'].sum().reset_index()
    df_all['总数占比'] = df_all['now_amount'] / df_all['start_amount']
    df_all['可用占比'] = df_all['available'] / df_all['now_amount']
    df_all = df_all[['now_amount', 'available', 'currency', 'start_amount', '可用占比', '总数占比']]
    return df_all


def DataTotuple(data):
    """
    create table amount_acc_sub(
    number int not null auto_increment,
    time datetime default current_timestamp on update current_timestamp,
    account_name varchar(10),
    available double,
    currency varchar(6),
    frozen double,
    now_amount double,
    start_amount double ,
    now_start_pro float(4,2),
    primary key (number , time ,currency)
    );

    create table amount_acc_total(
    number int not null auto_increment,
    time datetime default current_timestamp on update current_timestamp,
    amount_all double,
    available double,
    currency varchar(6),
    start_amount double,
    可用占比 double(4,2),
    总数占比 double(4,2),
    primary key (number , time ,currency)
    );
    """
    valuse = ''
    for re in data.values:
        valuse += f'{tuple(re)},'
    valuse = valuse[:-1]
    valuse = valuse.replace('nan', 'NULL')

    return valuse


async def get_wallet(apikey, start_amount_dict, account_name, symbol_list, id):
    """
    ['available': '1171977.606138558529858401',
        'currency': 'EOS',
        'frozen': '20976.495932761414632210',
        'start_amount': 1000000},
    ...]
    """
    ao = AApi(token=apikey['token'], secret_key=apikey['sk'])
    res = await ao.wallet()
    d = []
    if res['errno'] in [20529, 20522]:
        mess = f'【error】:ID：{id}：{res}'
        sendmessage.send_telegram_msg(message=mess, ser='EmerWarning')
    market_wallets = res["result"]
    for market_wallet in market_wallets:
        if market_wallet['currency'] in symbol_list:
            market_wallet["start_amount"] = start_amount_dict.get(market_wallet['currency'], 0)
            market_wallet["account_name"] = account_name
            market_wallet['now_amount'] = float(market_wallet['available']) + float(market_wallet['frozen'])
            d.append(market_wallet)
    return d


async def get_amount(symbol_list, spot_account_list, start_amount):
    tasks = []
    res = []

    for k in spot_account_list:
        account_name = k
        v = spot_account_list[k]
        apikey = v['apikey']
        id = v.get('id', {})
        start_amount_dict = start_amount.get(str(id), {})
        tasks.append(asyncio.create_task(get_wallet(apikey, start_amount_dict, account_name, symbol_list, id)))
    for t in tasks:
        res += (await t)
    df_account_all = pd.DataFrame(res)
    return df_account_all


# 读取配置参考值数据
async def read_mysql():
    sql = 'select * from reference_fund;'
    # sql = 'select * from me;'
    # results, title = get_data.read_mysql1(rds_db='spot', sql=sql)
    results, title = await G_MysqlSession.fetch_all(sql)
    temp = pd.DataFrame(list(results), columns=title)
    # for ti in title[2:]:
    #     temp['account_name'] = ti
    #     df = temp[['symbol', ti, 'account_name']]
    #     df.rename(columns={ti: 'reference_amount', 'symbol': 'currency'}, inplace=True)
    #     df_reference_fund = df_reference_fund.append([df], ignore_index=True)

    return temp


# 当前资金少于初始资金
async def acc_amount_pro(now):
    mess_quant_web = ""
    START_AMOUNT_SPOT, START_AMOUNT_CONTRACT = await infor_start_amount.get_start_amount()
    df_account_all = await get_amount(symbol_list=SYMBOLS_LIST, spot_account_list=spot_account_list, start_amount=START_AMOUNT_SPOT)
    df_reference_fund = await read_mysql()

    df = pd.merge(df_account_all, df_reference_fund, on=['account_name', 'currency'], how='left')
    df = df[['account_name', 'currency', 'frozen', 'now_amount', 'start_amount', 'reference_amount']]
    df['now_amount'] = df['now_amount'].astype(float)
    df['frozen'] = df['frozen'].astype(float)
    df['reference_amount'] = df['reference_amount'].astype(float)
    df = df[df['reference_amount'] != 0]
    df['pro'] = df['now_amount'] / df['reference_amount']
    df['pro_frozen'] = df['frozen'] / df['now_amount']
    dff = copy.deepcopy(df)
    # 初始值/当前参考值 < 0.2 报警 ------------------------------------------------------
    df = df[df['pro'] <= 0.2]
    if not df.empty:
        mes = f"【现货】当前资金少于参考资金的20%,需要划转\n"
        for i in range(len(df)):
            symbol = df['currency'].iloc[i]
            acc = df['account_name'].iloc[i]
            now_amount = int(df['now_amount'].iloc[i])
            reference_amount = (df['reference_amount'].iloc[i]).astype(int)
            proportion = (df['pro'].iloc[i] * 100).__round__(2)
            id = spot_account_list[acc]['id']
            Purpose = spot_account_list[acc]['Purpose']
            mes += f"【{symbol}】\n" \
                   f"账户:{acc}-{id}-{Purpose}\n" \
                   f"当前数量:{now_amount}\n" \
                   f"参考数量:{reference_amount}\n" \
                   f"数量占比:{proportion}%\n\n"

            mess_quant_web += f"<b style='color:#FF0000'>【{symbol}】 {acc}</b> 当前数量:{now_amount} 初始数量:{reference_amount} 占比:{proportion}%<br>"

        sendmessage.send_telegram_msg(message=f"{now}{mes}", ser='spot_info')
        print(f'{now} acc_amount_pro | 正常')
    monitor.get_a_monitor(event_name='bb_transfer', msg=mess_quant_web)

    # 初始值/当前参考值 < 0.2 报警
    dff['start_amount'] = dff['start_amount'].astype(float)

    dff['pro'] = dff['now_amount'] / dff['start_amount']
    dff = dff[(dff['pro'] <= 0.2) | (dff['start_amount'] <= 0)]
    if not dff.empty:
        msg = f"【现货】当前资金少于初始资金的20%,需要划转\n"
        for i in range(len(dff)):
            symbol = dff['currency'].iloc[i]
            acc = dff['account_name'].iloc[i]
            now_amount = int(dff['now_amount'].iloc[i])
            start_amount = (dff['start_amount'].iloc[i]).astype(int)
            proportion = (dff['pro'].iloc[i] * 100).__round__(2)
            id = spot_account_list[acc]['id']
            Purpose = spot_account_list[acc]['Purpose']
            msg += f"【{symbol}】\n" \
                   f"账户:{acc}-{id}-{Purpose}\n" \
                   f"当前数量:{now_amount}\n" \
                   f"初始数量:{start_amount}\n" \
                   f"数量占比:{proportion}%\n\n"
        sendmessage.send_telegram_msg(message=msg, ser='spot_info')


async def spot_run():
    try:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await acc_amount_pro(now)
        await heartbeat.i_live_well(server='现货数量监控', frequency=60 * 30, index=31)
    except Exception as e:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sendmessage.send_telegram_msg(message=f'{now} | error：acc_amount {e}', ser='Alarm')
        print(f'{now} | error : acc_amount -->> {e}')


if __name__ == "__main__":
    # asyncio.run(spot_run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(spot_run())
