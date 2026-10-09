# coding=utf-8
import os, sys, requests, time, re, asyncio
import loguru
import datetime
import traceback
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_hedge, infor, infor_load
from exchange.restful_api import binance, huobi, okex, gateio, mexc, abc_interfaces
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
from spot.spot_setting import getRate
from libs.requestSession import G_RequestSession
from libs.get_time import ATime
from spot.spot_exchange_deposit_withdraw_fee import get_deposit_withdraw_fee

exchange = infor_hedge.config_exchange['hedge']

exchange_apikey = {k: v['apikey'] for k, v in exchange.items()}

EXCHANGE_API = {
    'bn': binance.BinanceApi(**exchange_apikey['bn']),
    # 'hb': huobi.HuobiApi(**exchange_apikey['hb']),
    # 'okex': okex.OkexApi(**exchange_apikey['okex']),
    'gate': gateio.GateioApi(**exchange_apikey['gateio']),
    'mxc': mexc.MexcApi(**exchange_apikey['mxc']),
    'abc': abc_interfaces.AINTERFACES()

}
STATUS = {ex: {'deposit': v.deposit_status, 'withdraw': v.withdraw_status, } for ex, v in EXCHANGE_API.items()}

FAILED_WITHDRAWAL_STATUS = [status for k, v in STATUS.items() for code, status in v['withdraw'].items() if
                            any(i in status for i in ['拒绝', '错误', '失败', '无效', '撤销', '取消', '驳回'])]
SUCCESS_DEPOSIT_STATUS = [status for k, v in STATUS.items() for code, status in v['deposit'].items() if
                          any(i in status for i in ['成功', '已确认', '完成', '已汇出', '到账'])]

exchange = {
    '0xc822c6a88b5f99e42af2b7f03a51027c79908cfa': ['etherscan', 'https://api.etherscan.io/', 'ETH', 18,
                                                   [13365184, 13650499]],
    '0x0445A1a8eB70bD15dA537D65EA4Cfbd8f052E836': ['bscscan', 'https://api.bscscan.com/', 'BNB', 18,
                                                   [8080103, 12799663]],
    # '0xaE9D05eFf91e761cfb77A30d11b9536748a9aF83': ['hecoinfo', 'https://api.hecoinfo.com/', 'HT', 18,
    #                                                [5298702, 8565360]],
}


async def get_swap(address_all):
    # 主网链信息
    temp = []
    for k, v in exchange.items():
        print(f'-------------------swap_address {k, v}-------------------------------')
        startblock = v[4][0]
        url = f'{v[1]}api?module=account&action=txlist&address={k}&startblock=0&endblock=999999999&sort=desc&apikey={infor_BACKSTAGE.A_API_TOKEN}'
        async with G_RequestSession.request.request(method="GET", url=url, timeout=5) as r:
            if r.status == 200:
                for ret in r.json()['result']:
                    if ret['to'] in address_all or ret['from'] in address_all:
                        tmp = {}
                        tmp['exchange'] = v[0]
                        tmp['id'] = ''
                        tmp['currency'] = v[2]
                        tmp['address'] = ret['to']
                        tmp['hash'] = ret['hash']
                        tmp['amount'] = float(ret['value']) / 10 ** (float(v[3]))
                        tmp['fee'] = float(ret['gasPrice']) / 10 ** (float(v[3])) * float(ret['gasUsed'])
                        tmp['side'] = 'deposit' if ret['to'] in exchange.keys() else 'withdraw'
                        tmp['status'] = 'ok'
                        tmp['status1'] = '成功'
                        temp.append(tmp)

    # 代币信息
    for k, v in exchange.items():
        print(f'-----------------swap_contractaddress--{k, v}-------------------------------')
        startblock = v[4][1]
        url = f'{v[1]}api?module=account&action=tokentx&address={k}&startblock={startblock}&endblock=999999999&sort=desc&apikey=YourApiKeyToken'
        # res = requests.get(url, timeout=10).json()['result']
        async with G_RequestSession.request.request(method="GET", url=url, timeout=5) as r:
            if r.status == 200:
                for ret in r.json()['result']:
                    if ret['to'] in address_all or ret['from'] in address_all:
                        tmp = {}
                        tmp['exchange'] = v[0]
                        tmp['currency'] = ret['tokenSymbol']
                        tmp['address'] = ret['to']
                        tmp['hash'] = ret['hash']
                        tmp['amount'] = float(ret['value']) / 10 ** (float(ret['tokenDecimal']))
                        tmp['fee'] = float(ret['gasPrice']) / 10 ** (float(ret['tokenDecimal'])) * float(ret['gasUsed'])
                        tmp['type'] = 'deposit' if ret['to'] in exchange.keys() else 'withdraw'
                        tmp['status'] = 'ok'
                        tmp['status1'] = '成功'
                        temp.append(tmp)
            else:
                mess = f'去中心化获取数据状态错误：webhook_exchange_deposit_withdraw-->{v[1]}:{r.status_code}'
                sendmessage.send_telegram_msg(message=mess, ser='Alarm')

    return temp


async def deposit_withdraw_history(address_all):
    # res = await get_swap(address_all)
    res = []
    for ex, v in EXCHANGE_API.items():
        if ex == 'abc':
            user_id = infor_hedge.acc_id_xdc
            res_deposit = await v.deposit_history(user_id=user_id)
            res_withdraw = await v.withdraw_history(user_id=user_id)
        else:
            res_deposit = await v.deposit_history()
            res_withdraw = await v.withdraw_history()
        if type(res_deposit) == list and res_deposit:
            res += res_deposit
            loguru.logger.info(f'{ex} deposit:{len(res_deposit)} {res_deposit}')
            for i in res_deposit:
                address_all.append(i['address'].lower())
        if type(res_withdraw) == list and res_withdraw:
            res += res_withdraw
            loguru.logger.info(f'{ex} withdraw:{len(res_withdraw)} {res_withdraw}')
    if res:
        title = list(res[0].keys())
        values = ",".join([str(tuple(i[j] for j in title)) for i in res])
        title = ",".join(title)

        sql = f"insert ignore into exchange_deposit_withdraw ({title}) " \
              f"values {values}" \
              f"on duplicate key update " \
              f"status = values (status)," \
              f"status1 = values (status1)," \
              f"address = values (address)," \
              f"mtime = values (mtime)," \
              f"hash = values (hash)"

        await G_MysqlSession.insert_sql(sql=sql)


async def get_address_all():
    sql_address = "select distinct address from exchange_deposit_withdraw where side='deposit' and address<>'';"
    results, title = await G_MysqlSession.fetch_all(sql=sql_address)
    return [res[0].lower() for res in results]


async def run_message():
    DOY = 2
    message = ""
    deposit_and_withdrawal, message_deposit = {}, {}

    today = datetime.datetime.now()
    # 计算偏移量
    offset = datetime.timedelta(days=-DOY)
    # 获取想要的日期的时间
    re_date = (today + offset).strftime("%Y-%m-%d %H:%M:%S")
    sql = f"select * from exchange_deposit_withdraw where time >'{re_date}' and status <>'BCODE' and address not in {tuple(exchange.keys())} ;"
    results, title = await G_MysqlSession.fetch_all(sql=sql)
    df = pd.DataFrame(list(results), columns=title)

    df_deposit = df[df['side'] == 'deposit']
    df_withdrawal = df[df['side'] == 'withdraw']

    data = pd.merge(df_deposit, df_withdrawal, on=['hash'], how='outer')

    data = data.sort_values(by=["updatetime_y"], ascending=False)

    data['exchange_y'].fillna('无', inplace=True)
    data['exchange_x'].fillna('无', inplace=True)
    # data['amount_x'].fillna(0, inplace=True)
    # data['amount_y'].fillna(0, inplace=True)
    data.fillna(0, inplace=True)
    data.fillna(0, inplace=True)
    for i in range(len(data)):
        exchange_deposit = data['exchange_x'].iloc[i]
        exchange_withdrawal = data['exchange_y'].iloc[i]
        amount_deposit = data['amount_x'].iloc[i]
        amount_withdrawal = data['amount_y'].iloc[i]
        status_deposit = data['status_x'].iloc[i]
        status_withdrawal = data['status_y'].iloc[i]

        currency_deposit = data['currency_x'].iloc[i]
        currency_withdrawal = data['currency_y'].iloc[i]
        if currency_deposit in ["TRX"] and amount_deposit < 10 or currency_withdrawal in ["TRX"] and amount_withdrawal < 10:
            continue

        tx_hash = data['hash'].iloc[i]

        if amount_deposit + amount_withdrawal < 0.001:
            ROUND = 5
        elif amount_deposit + amount_withdrawal < 10:
            ROUND = 3
        else:
            ROUND = 1

        time_deposit = ATime().timestamp_to_timearray(data['mtime_x'].iloc[i]) if data['mtime_x'].iloc[i] else data['updatetime_x'].iloc[i]
        time_withdrawal = ATime().timestamp_to_timearray(data['mtime_y'].iloc[i]) if data['mtime_y'].iloc[i] else data['updatetime_y'].iloc[i]
        side_deposit = '无状态' if exchange_deposit == '无' else STATUS[exchange_deposit]['deposit']. \
            get(str(status_deposit), status_deposit)
        side_withdrawal = '无状态' if exchange_withdrawal == '无' else STATUS[exchange_withdrawal]['withdraw']. \
            get(str(status_withdrawal), status_withdrawal)

        # 有提币，无充币 1、拒绝 不用报警 2、其他状态需要报警
        if exchange_withdrawal != '无' and exchange_deposit == '无':
            if side_withdrawal not in FAILED_WITHDRAWAL_STATUS:
                message += f"提币：{round(amount_withdrawal, ROUND)}{currency_withdrawal}[{exchange_withdrawal},{side_withdrawal},{time_withdrawal}]\n"

                deposit_and_withdrawal[currency_withdrawal] = deposit_and_withdrawal.get(currency_withdrawal, 0) \
                                                              + amount_withdrawal * (-1)

        # 有充提，1、充币状态成功不用报警 2、充币其他状态有需要报警
        elif exchange_withdrawal != '无' and exchange_deposit != '无':
            if side_deposit not in SUCCESS_DEPOSIT_STATUS:
                message += f"提币：{round(amount_withdrawal, ROUND)}{currency_withdrawal}[{exchange_withdrawal},{side_withdrawal},{time_withdrawal}]\n" \
                           f"充币：{round(amount_deposit, ROUND)}{currency_deposit}[{exchange_deposit},{side_deposit},{time_deposit}]\n\n"

                deposit_and_withdrawal[currency_withdrawal] = deposit_and_withdrawal.get(currency_withdrawal, 0) \
                                                              + amount_withdrawal * (-1)
        # 没有提币，只用充币 都需要报警.
        elif exchange_withdrawal == '无' and exchange_deposit != '无':
            message_deposit[
                tx_hash] = f"充币：{round(amount_deposit, ROUND)}{currency_deposit}[{exchange_deposit},{side_deposit},{time_deposit}]\n"

            # message += f"充币：{round(amount_deposit, ROUND)}{currency_deposit}[{exchange_deposit},{side_deposit},{time_deposit}]\n\n"
            deposit_and_withdrawal[currency_deposit] = deposit_and_withdrawal.get(currency_deposit, 0) \
                                                       + amount_deposit * (1)

    # 没有提币，只有充币 1 那数据时间的原因，通过hash再次获取数据
    if message_deposit:
        if len(message_deposit) == 1:
            hash_message_deposit = list(message_deposit.keys())[0]
            sql_hash = f"hash = '{hash_message_deposit}' "
        else:
            hash_message_deposit = tuple(message_deposit.keys())
            sql_hash = f"hash in {hash_message_deposit} "
        sql_withdrawal = f"select * from exchange_deposit_withdraw  where side='withdraw' and {sql_hash} ;"
        res_withdrawal, title_withdrawal = await G_MysqlSession.fetch_all(sql=sql_withdrawal)
        df_withdrawal_hash = pd.DataFrame(list(res_withdrawal), columns=title_withdrawal)
        if not df_withdrawal_hash.empty:
            for i in range(len(df_withdrawal_hash)):
                tx_hash = df_withdrawal_hash['hash'].iloc[i]

                if tx_hash in list(message_deposit.keys()):
                    amount_withdrawal = df_withdrawal_hash['amount'].iloc[i]
                    currency_withdrawal = df_withdrawal_hash['currency'].iloc[i]

                    deposit_and_withdrawal[currency_withdrawal] = deposit_and_withdrawal.get(currency_withdrawal, 0) \
                                                                  + amount_withdrawal * (-1)

                    message_deposit.pop(tx_hash)

    for k, v in message_deposit.items():
        message += v

    # Todo 资金划转去理财
    sql_financial_products = f"select symbol,sum(amount) amount from financial_products where time >='{re_date}' group by symbol"
    res_financial_products, title_financial_products = await G_MysqlSession.fetch_all(sql=sql_financial_products)
    financial_products = pd.DataFrame(list(res_financial_products), columns=title_financial_products)
    if res_financial_products:
        dict_financial_products = dict(zip(financial_products['symbol'], financial_products['amount']))
        message += f'理财：{dict_financial_products}\n'
        for k, v in dict_financial_products.items():
            if k in deposit_and_withdrawal.keys():
                deposit_and_withdrawal[k] += v * (-1)
            else:
                deposit_and_withdrawal[k] = v * (-1)

    if message != '':
        rate = await getRate(infor.SYMBOLS_PAIR)
        deposit_and_withdrawal = {k: f"{round(v, 3)}[U:{float(rate.get(k + '-USDT', 0)) * v}" for k, v in
                                  deposit_and_withdrawal.items() if v}

        # deposit_and_withdrawal = {
        #     k: f"{float('%.3g' % v)}[U:{int(float(rate[k + '-USDT']) * v) if k + '-USDT' in rate.keys() else 0}]" for k, v
        #     in deposit_and_withdrawal.items() if v != 0 and v != None}

        if deposit_and_withdrawal:
            message += f'\n累计记录近{DOY}天:\n' + str(deposit_and_withdrawal)
            MESSAGE = f'{re_date}-{today}\n<因为存在不确定因素，此信息只作为参考>\n近{DOY}天充提记录\n' + message

            sendmessage.send_telegram_msg(MESSAGE, ser='spot_info')


async def spot_run1():
    address_all = await get_address_all()
    while True:
        try:
            # timestamp = int((time.time() - 5 * 60 * 60 * 24) * 1000)
            await deposit_withdraw_history(address_all)
            await run_message()
            await heartbeat.i_live_well(server='各个交易所充提监控', frequency=60 * 16, index=29)
            time.sleep(5 * 60)
        except Exception as e:
            mm = traceback.format_exc()
            mess = f'error：webhook_exchange_deposit_withdraw-->{e}\n{mm}'
            sendmessage.send_telegram_msg(message=mess, ser='Alarm')
            time.sleep(2 * 60)
        address_all = list(set(address_all))


async def spot_run():
    # address_all = await get_address_all()
    # print(address_all)
    address_all = []
    await deposit_withdraw_history(address_all)
    await run_message()
    await get_deposit_withdraw_fee()  # 统计充提手续费
    await heartbeat.i_live_well(server='各个交易所充提监控', frequency=60 * 60 * 2, index=29)

    # while True:
    #     try:
    #         # timestamp = int((time.time() - 5 * 60 * 60 * 24) * 1000)
    #         await deposit_withdraw_history(address_all)
    #         await run_message()
    #         await heartbeat.i_live_well(server='各个交易所充提监控', frequency=60 * 16, index=29)
    #         time.sleep(5 * 60)
    #     except Exception as e:
    #         mm = traceback.format_exc()
    #         mess = f'error：webhook_exchange_deposit_withdraw-->{e}\n{mm}'
    #         sendmessage.send_telegram_msg(message=mess, ser='Alarm')
    #         time.sleep(2 * 60)
    #     address_all = list(set(address_all))


if __name__ == '__main__':
    # asyncio.run(spot_run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(spot_run())
