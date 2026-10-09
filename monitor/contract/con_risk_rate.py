#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, datetime
import pandas as pd
import urllib3
import asyncio
import traceback
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import monitor
from config.infor_contract import contract_account, SYMBOLS_CONTRACT_PAIR
from exchange.restful_api.abc_contract import AApi
from libs import requestSession, sendmessage, heartbeat
from contract.contract_setting import get_precision, get_symbols_details, getRate, CAPITAL_RATE_PARAM, get_capital_rate_param, sleep_time

# 不提示警告
pd.set_option('mode.chained_assignment', None)

# 监控哪些账户
acc_contract_list = list(contract_account.keys())

RISK_RATE = 500
AMOUNT_COEF = 2
POSITION_U = 10000 * 5
Type = {1: '多仓', 2: '空仓'}  # 1多仓，2空仓
fetch_timeout = 60 * 20


async def get_account_position(apikey, account, amount_coef):
    ao = AApi(token=apikey['token'], secret_key=apikey['sk'])
    res = await ao.position_contract()
    d = []
    if res['errno'] == 0 and res['result'] != []:
        for re in res['result']:
            temp = {}
            temp['account'] = account
            temp['symbol'] = re['symbol']
            temp['type'] = re['type']  # 1多仓，2空仓
            temp['risk_rate'] = re['risk_rate']  # 风险率
            temp['avail_amount'] = float(re['avail_amount'])  # 可平数量(张数)
            temp['amount'] = float(re['amount'])  # 持有数量
            temp['contract_frozen'] = float(re['contract_frozen'])  # 委托冻结(张数)
            temp['open_price_avg'] = float(re['open_price_avg'])  # 开仓均价
            temp['equity'] = float(re['equity'])  # 账户权益(USDT)
            temp['avail'] = float(re['avail']) if re['avail'] else 0  # 可用(USDT)
            temp['bood'] = float(re['bood'])  # 冻结保证金(USDT)
            temp['profit'] = float(re['profit'])  # 可用(USDT)
            temp['amount_coef'] = amount_coef
            d.append(temp)

    return d


async def getpositon():
    tasks = []
    res = []
    for k, v in contract_account.items():
        apikey = v['apikey']
        amount_coef = v['boundary_amount']
        tasks.append(asyncio.create_task(get_account_position(apikey, k, amount_coef)))
    for t in tasks:
        res += (await t)
    return res


async def positon(df_symbols_details):
    res = await getpositon()
    rate = await getRate(SYMBOLS_CONTRACT_PAIR=SYMBOLS_CONTRACT_PAIR)
    df_rate = pd.DataFrame([{'symbol': k, 'rate': v} for k, v in rate.items()])
    df = pd.DataFrame(res)
    df = pd.merge(df, df_symbols_details, left_on='symbol', right_on='symbol', how='left')
    df = pd.merge(df, df_rate, left_on='symbol', right_on='symbol', how='left')
    df = df[['id', 'account', 'avail_amount', 'symbol', 'risk_rate', 'contract_size', 'amount', 'open_price_avg', 'type', 'max_size', 'amount_coef', 'rate']]
    # print(df[['symbol', 'amount', 'Amount', 'open_price_avg', 'type', 'id']][df['open_price_avg'] == 0])
    df['contract_size'] = df['contract_size'].astype(float)
    df['max_size'] = df['max_size'].astype(float)  # 最大交易数量
    # df['usdt'] = df['open_price_avg'] * df['contract_size'] * df['amount']
    df['usdt'] = df['amount'] * df['rate'] * df['contract_size']
    # print(df[['id', 'symbol', 'id', 'amount','max_size']][df['symbol'] == 'AGLD-USDT'])
    # temp_risk_rate = pd.DataFrame()
    # temp_risk_rate = df[(df['risk_rate'] > 0) & (df['risk_rate'] < RISK_RATE)]
    df['coef'] = df['amount'] / df['max_size']
    temp_risk_rate = df[(df['coef'] > df['amount_coef'])]

    temp = df.groupby(['symbol', 'type', 'max_size', 'contract_size'])[['amount', 'usdt']].sum().reset_index()
    temp['coef'] = temp['amount'] / temp['max_size']
    temp = temp[temp['coef'] > AMOUNT_COEF]

    # common_symbol = list(set(list(temp['symbol'][temp['type'] == 1])) & set(list(temp['symbol'][temp['type'] == 2])))
    # temp = temp[temp['symbol'].isin(common_symbol)]
    #  Type = {1: '多仓', 2: '空仓'}
    df['side'] = 1
    df['side'][df['type'] == 2] = -1
    df['usdt'] = df['side'] * df['usdt']
    df['amount'] = df['amount'] * df['side']

    return df, temp_risk_rate


def get_mess(temp):
    mes, mess_quant_web = "", ""
    if not temp.empty:
        accounts = list(temp['account'].unique())
        for account in accounts:
            temp_acc = temp[temp['account'] == account]
            Acc = contract_account[account]
            purpose = Acc['purpose']
            id = Acc['id']
            coef = Acc['boundary_amount']
            mes += f"{account}-{purpose}-{id} (>{coef}倍)\n"
            for i in range(len(temp_acc)):
                type = Type[temp_acc['type'].iloc[i]]
                symbol = temp_acc['symbol'].iloc[i]
                risk_rate = temp_acc['risk_rate'].iloc[i]
                amount = temp_acc['amount'].iloc[i]
                usdt = temp_acc['usdt'].iloc[i]
                avail_amount = temp_acc['avail_amount'].iloc[i]
                mes += f"   {symbol}-{type},风险率:{risk_rate},持仓张数:{amount},可平张数:{avail_amount},价值:{int(usdt)}\n"
                mess_quant_web += f"<b style='color:#FF0000'>{symbol}</b>  {purpose} <b style='color:#FF0000'>持仓张数:{amount}</b> 可平张数:{avail_amount}价值:{int(usdt)}<br>"

    return mes, mess_quant_web


async def get_positon(df_symbols_details):
    # 第一次获取合约精度
    df, temp_risk_rate = await positon(df_symbols_details)

    # 净持仓
    df_position = df.groupby(['symbol'])[['amount', 'usdt']].sum().reset_index()
    df_position = df_position[abs(df_position['usdt']) >= POSITION_U]
    mess_quant_web = ""
    if not df_position.empty:
        msg = f"👌*合约量化净持仓*👌\n" \
              f"*量化账户净持仓>{POSITION_U}U ({int(fetch_timeout / 60)}min/次)*\n" \
              f"资金费用:结算前20-30min(10min/次),结算前10min(2min/次)\n"
        df_position = df_position.reindex(df_position["usdt"].abs().sort_values(ascending=True).index)
        for i in range(len(df_position)):
            symbol = df_position['symbol'].iloc[i]
            amount = df_position['amount'].iloc[i]
            usdt = df_position['usdt'].iloc[i]
            msg += f"【{symbol}】\n" \
                   f"         仓位:{int(amount)}张 ({int(usdt)}U)\n"
        sendmessage.send_telegram_msg_mdv2(msg, ser='contract_info_user')
        mess_quant_web = msg
    monitor.get_a_monitor(event_name='one_user_position', msg=mess_quant_web)

    # 风险率
    mes, mess_quant_web = "", ""
    mes_risk_rate, mess_quant_web_risk_rate = "", ""
    if not temp_risk_rate.empty:
        accounts = list(temp_risk_rate['account'].unique())
        for account in accounts:
            temp_acc = temp_risk_rate[temp_risk_rate['account'] == account]
            Acc = contract_account[account]
            purpose = Acc['purpose']
            id = Acc['id']
            coef = Acc['boundary_amount']
            mes += f"{account}-{purpose}-{id} (>{coef}倍)\n"
            for i in range(len(temp_acc)):
                type = Type[temp_acc['type'].iloc[i]]
                symbol = temp_acc['symbol'].iloc[i]
                risk_rate = temp_acc['risk_rate'].iloc[i]
                amount = temp_acc['amount'].iloc[i]
                usdt = temp_acc['usdt'].iloc[i]
                if pd.isna(usdt):
                    continue
                avail_amount = temp_acc['avail_amount'].iloc[i]
                mes += f"   {symbol}-{type},持仓张数:{amount},可平张数:{avail_amount},价值:{int(usdt)}\n"
                mess_quant_web += f"<b style='color:#FF0000'>{symbol}</b>  {purpose} <b style='color:#FF0000'>持仓张数:{amount}</b> 可平张数:{avail_amount}价值:{int(usdt)}<br>"

    if mes != '':
        message = f'【合约量化持仓】张数 大于{AMOUNT_COEF}倍的最大持仓量 ({int(fetch_timeout / 60)}min/次)\n全仓和逐仓都需要查询一下。多空都持仓量较大，排查平仓服务是否异常\n{mes}'
        print(message)
        # sendmessage.send_telegram_msg(message, ser='contract_info_user')
    if mes_risk_rate != '':
        message = f'【合约持仓风险率】低于{RISK_RATE}\n{mes_risk_rate}'
        sendmessage.send_telegram_msg(message, ser='contract_info_user')
        # sendmessage.send_telegram_msg(message, ser='EmerWarning')

    # monitor.get_a_monitor(event_name='risk_rate', msg=mess_quant_web + mess_quant_web_risk_rate)


async def get_positon_amount():
    df_symbols_details = pd.DataFrame(get_symbols_details())
    while True:
        try:
            await get_positon(df_symbols_details)
            await heartbeat.i_live_well(server='合约风险率', frequency=fetch_timeout * 2.5, index=33)
            logger.info(f" contract_risk_rate wait 2min")
            # await asyncio.sleep(sleep_timeout)
        except:

            mm = traceback.format_exc()
            sendmessage.send_telegram_msg(f'A_precision\n{mm}', ser='Alarm')
            logger.error(f" error:contract_risk_rate")
            # await asyncio.sleep(sleep_timeout / 2)
        finally:
            ts = await sleep_time(PARAM=CAPITAL_RATE_PARAM, fetch_timeout=fetch_timeout)
            await asyncio.sleep(max(ts, 60 * 1))


async def contract_run():
    task = [
        get_positon_amount(),
        get_capital_rate_param()
    ]
    await asyncio.gather(*task)


if __name__ == '__main__':
    asyncio.run(contract_run())
