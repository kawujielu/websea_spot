# coding=utf-8
import pandas as pd
import numpy as np
import os, sys
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, infor_hedge, monitor, infor_swap, infor_load
from libs import heartbeat, sendmessage, get_time
from libs.database.getmongo import G_MongodbSession
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession
from spot.spot_setting import getRate, getRateUsdt, get_pool_threshold, get_pool, get_mongo_amount
from exchange.mdex_libs.mdex import *
from exchange.restful_api.abc_spot import AApi
import json, ccxt, copy, asyncio, collections, datetime, time, random, math, sys
from web3 import Web3
from bson.objectid import ObjectId
from datetime import datetime, timedelta, date
from spot.spot_get_mongo_w_order import spot_run as spot_order

# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = infor.acc_id
xdc = [infor_hedge.config_exchange['hedge']['xdc']['uid']]
SYMBOL = []
SYMBOLS_LIST = list(set(infor.SYMBOLS_LIST + SYMBOL))

CURRENCY_OUT = [s.plint('-')[0] for s in infor.SYMBOLS_OUT + SYMBOL] + ['USDT']
CURRENCY_HANDLE_HEDGE = [s.plint('-')[0] for s in infor.SYMBOLS_HANDLE_HEDGE + SYMBOL] + ['USDT']
COFE_FEE_pig = {'PIG': 0.95}

COEF = 1.2
# 统计对冲头寸与对冲池头寸差值
POOL_STAT_U = 25000
# 头寸超过的阈值
THRESHOLD_U = 1000000
# 手动对冲数量
HANDLE_AMOUNT = 1000
# 手动对冲价值的U
HANDLE_AMOUNT_U = 4000
AMOUNT_USDT = 100 * 10000


# # 获取对冲阈值
class hedge():
    # start_time = 1569600000  # '2019-09-28 00:00:00
    # start_time_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1569600000))
    start_time_dt = '2023-06-01 00:00:00'
    start_time = timestamp = time.mktime(time.strptime(start_time_dt, "%Y-%m-%d %H:%M:%S")).__int__()

    def get_monthstart_daystart(self):
        now = date.today()
        this_day_start = now.strftime("%Y-%m-%d %H:%M:%S")
        this_month_start = datetime(now.year, now.month, 1)
        this_month_start = str(this_month_start)
        return this_month_start, this_day_start

    def today_zero(self):
        timezone = int(time.time() - int(time.time() - time.timezone) % 86400)
        timezone_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timezone))

        return timezone, timezone_dt

    # # 每15min 运行一次
    # def today_zero_naxt(self):
    #     zeroPoint = (int(time.time()) - int(time.time() - time.timezone) % 86400) + 7 * 60  # 31 * 60
    #     zeroPoint_dt = setting_quant.timestamp_to_timearray(zeroPoint)
    #     return zeroPoint_dt

    # 凌晨提笔零时处理
    async def get_profit_loss_brief(self, this_day_start):
        sql = f'select currency,sum(amount) from spot_profit_loss_brief where time >= "{this_day_start}" group by currency'
        result, title = await G_MysqlSession.fetch_all(sql=sql)
        result = {i[0]: i[1] for i in result}
        if result:
            sql = f"SELECT currency,`rate|U`,time from hedge WHERE time = (SELECT time FROM hedge WHERE time >= '{this_day_start}' order by time asc limit 1);"
            rate, title = await G_MysqlSession.fetch_all(sql=sql)
            rate = {i[0]: i[1] for i in rate}
            return sum([v * rate.get(s, 0) for s, v in result.items()])
        else:
            return 0

    # 划转
    async def mysql_transfer(self, start_time, END_TIME):
        sql_transfer = f'select * from exchange_transfer where time between "{start_time}" and "{END_TIME}" '
        result, title = await G_MysqlSession.fetch_all(sql=sql_transfer)
        result = [dict(zip(title, i)) for i in result]
        acc_dc = {}
        for i in result:
            coin = i['symbol']
            amount = i['amount']
            from_id = str(i['from_id'])
            to_id = str(i['to_id'])
            if from_id in acc_id and to_id in xdc:
                acc_dc[coin] = acc_dc.get(coin, 0) + amount
            elif from_id in xdc and to_id in acc_id:
                acc_dc[coin] = acc_dc.get(coin, 0) - amount
        return acc_dc

    # 理财
    async def mysql_financial_products(self, start_time, END_TIME):
        sql = f'select symbol,sum(amount) amount from financial_products ' \
              f'where time between "{start_time}" and "{END_TIME}"  group by symbol'
        result, title = await G_MysqlSession.fetch_all(sql=sql)
        FINANCING_AMOUNT = {k: v for k, v in result}
        return FINANCING_AMOUNT

    def colorize(self, num):
        color = 'yellow' if (np.isnan(num) or abs(num) > 50000) else ''
        return 'background-color: %s' % color

    def swap_restful(self):
        swap_Wallet = {}
        other_address = {
            'etherscan': {
                'USDC': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                'USDT': '0xdac17f958d2ee523a2206206994597c13d831ec7', },
            'bscscan': {
                # 'BNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',
                'USDT': '0x55d398326f99059ff775485246999027b3197955',
                'BUSD': '0xe9e7cea3dedca5984780bafc599bd69add087d56',
                'USDC': '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d', },
            'heco': {
                # 'WHT': '0x5545153ccfca01fbd7dd11c0b23ba694d9509a6f',
                'USDT': '0xa71edc38d189767582c38a3145b5873052c3e47a', }, }

        for chain_name, node_mappers in infor_swap.DEX_NODE_MAPPERS.items():
            for address in node_mappers['address']:
                swap_wallet = {}
                self_s = MdexSwap(address=address, node_url=random.choice(node_mappers['node_pools']))
                swap_wallet[node_mappers['chain_currency']] = self_s.get_eth_balance() / math.pow(10, 18)
                for pools_mappers in node_mappers['node_pools_mappers']:
                    for currency, contract_address in pools_mappers.items():
                        symbol = contract_address['pair_name']
                        base, quote = symbol.split('-')
                        pair_address = contract_address['pair_address']
                        first_address = contract_address['first_address']
                        second_address = contract_address['second_address']
                        if currency == base:
                            contractaddress = first_address
                        else:
                            currency = quote
                            contractaddress = second_address
                        if currency in SYMBOLS_LIST:
                            heco_first = self_s.erc20_contract(Web3.toChecksumAddress(contractaddress))
                            first_decimal = int(heco_first.functions.decimals().call())
                            volume_first = heco_first.functions.balanceOf(Web3.toChecksumAddress(address)).call() / math.pow(10, first_decimal)
                            swap_wallet[currency] = volume_first
                for currency, contractaddress in other_address[chain_name].items():
                    heco_first = self_s.erc20_contract(Web3.toChecksumAddress(contractaddress))
                    first_decimal = int(heco_first.functions.decimals().call())
                    volume_first = heco_first.functions.balanceOf(Web3.toChecksumAddress(address)).call() / math.pow(10, first_decimal)
                    swap_wallet[currency] = volume_first

                name = node_mappers['chain_name'] + str(node_mappers['address'].index(address)) if node_mappers['address'].index(address) else node_mappers['chain_name']
                swap_Wallet[name] = swap_wallet
        return swap_Wallet

    async def ccxt_wallet(self, ccxt_name, api, last):
        try:
            res = getattr(ccxt, ccxt_name)(api).fetch_balance()['total']
            temp = {k: v for k, v in res.items() if v}
            res = {'now': temp, 'start': last, 'side': 0}
        except Exception as e:
            logger.error(f'error {ccxt_name=}')
            res = {'now': {}, 'start': last, 'side': 1}
            sendmessage.send_telegram_msg(f'交易所获取钱包失败:{ccxt_name, e}', 'spot_ProfitLoss')
        return res

    async def exchange_wallet_1(self):
        wallet = {}
        tasks = []
        for k, ex_info in infor_hedge.config_exchange['hedge'].items():
            api = ex_info['apikey']
            ccxt_name = ex_info['Exchange']
            last = ex_info['start_amount']
            res = asyncio.create_task(self.ccxt_wallet(ccxt_name, api, last))
            tasks.append([k, res])

        for [k, t] in tasks:
            wallet[k] = await t
        return wallet

    async def exchange_wallet(self):
        exchange_wallets = {'bn': {'now': {}, 'start': {}, 'side': 0}, 'okex': {'now': {}, 'start': {}, 'side': 0},
                            'gateio': {'now': {}, 'start': {}, 'side': 0}, 'mxc': {'now': {}, 'start': {}, 'side': 0},
                            'bitget': {'now': {}, 'start': {}, 'side': 0}, 'kraken': {'now': {}, 'start': {}, 'side': 0},
                            'xdc': {'now': {}, 'side': 0}, }
        spec_ex_currency = {}
        spec_ex_currency_pr = {}
        for ex, v in infor_load.spec_symbol_rate_mapping_currency.items():
            spec_ex_currency[ex] = {j['name']: i for i, j in v.items()}
            spec_ex_currency_pr[ex] = {j['name']: 1 / j['pr'] for i, j in v.items()}
        for k, ex_info in infor_hedge.config_exchange['hedge'].items():
            api = ex_info['apikey']
            last = ex_info.get('start_amount', {})
            if k in ['bn', 'gateio', 'kraken']:  # 'mxc', 'bitget'
                ccxt_name = ex_info['exchange']
                # todo
                res = await self.ccxt_wallet(ccxt_name, api, last)
                if spec_ex_currency.get(k):
                    res['now'] = {spec_ex_currency.get(k).get(i, i): float(j) * spec_ex_currency_pr.get(k).get(i, 1) for i, j in res['now'].items()}
                exchange_wallets[k] = res
            elif k == 'xdc':
                ao = AApi(token=api['apiKey'], secret_key=api['secret'], flag='user')
                wallet = await ao.wallet()
                {'errno': 0, 'errmsg': 'success', 'result': [
                    {'currency': 'USDT', 'available': '361.36534106', 'frozen': '0.002195000000000001'}, 
                    {'currency': 'USDC', 'available': '-4210.881938102', 'frozen': '0.000601'}, 
                    {'currency': 'WBS', 'available': '6.000000016823379879', 'frozen': '0'}, 
                    {'currency': 'TRX', 'available': '-1893.2034326', 'frozen': '0.000001'}, 
                    {'currency': 'AXS', 'available': '0.322319435193984818', 'frozen': '0'}, 
                    {'currency': 'ARB', 'available': '-303.49887005', 'frozen': '0.000000000000000004'}, 
                    {'currency': 'INJ', 'available': '0.48754254', 'frozen': '0'}, 
                    {'currency': 'HOME', 'available': '664.047904482', 'frozen': '0'}, 
                    {'currency': 'ERA', 'available': '23.981642118174', 'frozen': '0'}, 
                    {'currency': 'PEOPLE', 'available': '264.047175', 'frozen': '0'}, 
                    {'currency': 'MOVE', 'available': '153.8707283852', 'frozen': '0'}, 
                    {'currency': 'USDR', 'available': '11.42599', 'frozen': '0'}, 
                    {'currency': 'EURR', 'available': '76.52001501881628464', 'frozen': '0'}]}
                
                wallet = {i['currency']: float(i['available']) + float(i['frozen']) for i in wallet["result"] if float(i['available']) or float(i['frozen'])}
                # wallet.update(diff_currency)
                # for k, v in diff_currency.items():
                #     if k in wallet:
                #         wallet[k] = v + diff_currency[k]
                #     else:
                #         wallet[k] = v
                exchange_wallets[k] = {'now': wallet, 'side': 0}
                
        # print(f"exchange_wallets值:{exchange_wallets}")
        return exchange_wallets

    async def get_data_run(self, rate, hedge_pool, hedge_threshold):
        global HEARTBEAT
        # ----------------------------------------------------------------------------------------------------
        this_month_start, this_day_start = self.get_monthstart_daystart()
        today_time, today_time_dt = self.today_zero()

        if int(time.time()) - today_time <= 5 * 60:
            time.sleep(5 * 60)
            today_time, today_time_dt = self.today_zero()

        now_time = time.time().__int__()
        now_time_dt = get_time.ATime().timestamp_to_timearray(now_time)

        # 交易所钱包 ----------------------------------------------------------------------------------------------------
        exchange_wallets = await self.exchange_wallet()
        logger.info("{exchange_wallets=}")

        HEARTBEAT = 0
        for ex, v in exchange_wallets.items():
            HEARTBEAT += v['side']

        # 链上钱包数据 ----------------------------------------------------------------------------------------------------
        swap_rest = {} # self.swap_restful()
        logger.info(f"{swap_rest=}")

        # 划转 ----------------------------------------------------------------------------------------------------
        acc_dc = await self.mysql_transfer(start_time=self.start_time_dt, END_TIME=now_time_dt)

        # 资金理财----------------------------------------------------------------------------------------------------
        FINANCING_AMOUNT = await self.mysql_financial_products(start_time=self.start_time_dt, END_TIME=now_time_dt)
        # mongo ----------------------------------------------------------------------------------------------------
        demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(today_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(now_time))}}
        asset_position = await G_MongodbSession.asset_position_process(demand=demand, acc_id=acc_id)

        mongo, asset_position = await get_mongo_amount(now_time_dt, asset_position)

        temps = []
        for k in SYMBOLS_LIST:
            temp = collections.OrderedDict()
            temp['time'] = now_time_dt
            temp['currency'] = k
            temp['binance当前值'] = exchange_wallets['bn']['now'].get(k, 0)
            temp['binance初始值'] = exchange_wallets['bn']['start'].get(k, 0)
            temp['okex当前值'] = exchange_wallets['okex']['now'].get(k, 0)
            temp['gate当前值'] = exchange_wallets['gateio']['now'].get(k, 0)
            temp['mxc当前值'] = exchange_wallets['mxc']['now'].get(k, 0)
            temp['bitget当前值'] = exchange_wallets['bitget']['now'].get(k, 0)
            temp['kraken当前值'] = exchange_wallets['kraken']['now'].get(k, 0)
            temp['理财'] = FINANCING_AMOUNT.get(k, 0)
            temp['eth'] = swap_rest.get('etherscan', {}).get(k, 0)
            temp['eth_dc'] = swap_rest.get('etherscan1', {}).get(k, 0)
            temp['bsc'] = swap_rest.get('bscscan', {}).get(k, 0)
            temp['heco'] = swap_rest.get('heco', {}).get(k, 0)

            temp['dc当前值'] = exchange_wallets['xdc']['now'].get(k, 0)
            now_am = temp['binance当前值'] + temp['okex当前值'] + temp['gate当前值'] + temp['mxc当前值'] + temp['bitget当前值'] + + temp['kraken当前值']
            sta_am = temp['binance初始值']
            swa_am = temp['eth'] + temp['eth_dc'] + temp['bsc'] + temp['heco']
            temp['对冲账户余额'] = temp['dc当前值'] + temp['理财'] + now_am + swa_am - sta_am
            # print(f"349行 {k} 对冲账户余额: {temp['对冲账户余额']}= {temp['dc当前值']} + {temp['理财']} + {now_am} + {swa_am} - {sta_am}")

            temp['mongodb'] = mongo.get(k, 0) + asset_position.get(k, 0)  # 今日用户盈亏+今日现货账户余额？？？
            temp['acc_dc'] = acc_dc.get(k, 0)   # 所有划转记录
            temp['量化差值'] = temp['mongodb'] - temp['acc_dc']
            # print(f"350行 {k} 量化差值: {temp['量化差值']} = {temp['mongodb']} - {temp['acc_dc']}")
            temp['人工做市差值'] = infor.START_AMOUNT_DICT_MAN.get(k, 0)
            temp['校正数据'] = infor.CORRECT_AMOUNT.get(k, 0)

            rate_u = rate.get(k, 0)
            temp['rate|U'] = rate_u
            # 对冲头寸 = 今日用户盈亏+今日现货账户余额+今日划转金额+对冲账户余额+人工做市差值(代码逻辑所有币对一直是0)+校正数据(一个写死的固定值)
            temp['对冲头寸'] = temp['量化差值'] + temp['对冲账户余额'] + temp['人工做市差值'] + temp['校正数据']
            # print(f"352行 {k} 对冲头寸: {temp['对冲头寸']}= {temp['量化差值']} + {temp['对冲账户余额']} + {temp['人工做市差值']} + {temp['校正数据']}")
            temp['对冲头寸|U'] = temp['对冲头寸'] * rate_u
            # print(f"355行 {k} 对冲头寸|U: {temp['对冲头寸|U']}= {temp['对冲头寸']} * {rate_u}")
            temp['对冲行为'] = 'SELL' if temp['对冲头寸'] > 0 else 'BUY' if temp['对冲头寸'] < 0 else '-'
            temp['对冲数量'] = abs(temp['对冲头寸'])
            # 参考—对冲阈值
            threshold = hedge_threshold.get(k, {})
            temp['对冲阈值'] = threshold['threshold'] if threshold.get('threshold', 0) else 10000 / rate_u if rate_u else 10000
            temp['对冲池'] = hedge_pool.get(k, 0)   # - abc_asset_gap 现货内部敞口统计 external_asset_gap 现货外部敞口统计 fee_asset_gap 充提手续费统计 3张表的总和
            temp['对冲状态'] = threshold.get('status', '-')
            temp['对冲交易所'] = threshold.get('hedeg_ex', '没有配置对冲')

            temp['对冲池|U'] = temp['对冲池'] * rate_u

            temp['coef_pool_stat'] = round(temp['对冲池'] / temp['对冲阈值'], 2) if temp['对冲阈值'] and k not in CURRENCY_HANDLE_HEDGE else 0
            temp['coef_stat_threshold'] = round(temp['对冲头寸'] / temp['对冲阈值'], 2) if temp['对冲阈值'] and k not in CURRENCY_HANDLE_HEDGE else 0
            temp['coef_pool_threshold'] = round(temp['对冲池'] / temp['对冲阈值'], 2) if temp['对冲阈值'] and k not in CURRENCY_HANDLE_HEDGE else 0
            temp['pool_stat'] = temp['对冲头寸'] * temp['对冲池']
            temp['pool_stat_u'] = temp['对冲头寸|U'] - temp['对冲池|U']

            temps.append(temp)
        data = pd.DataFrame(temps, index=None)

        title = list(data.columns)[:-7]
        get_mysql_data = data[title]

        # 储存数据库 ---------------------------------------------------------------------------------------------------------
        values = ','.join([f"{tuple(i)}" for i in get_mysql_data.values])

        title_sql = ','.join([f"`{i}`" for i in title])
        sql = f"insert into hedge ({title_sql}) values {values} ;"

        await G_MysqlSession.insert_sql(sql=sql)

        # 超过对冲阈值 预警 ---------------------------------------------------------------------------------------------------
        df_1 = data[['currency', 'rate|U', '对冲行为', '对冲数量', '对冲阈值', '对冲头寸|U', 'coef_stat_threshold',
                     '对冲交易所', '对冲池', '对冲状态', '对冲池|U', 'coef_pool_threshold', 'pool_stat', 'pool_stat_u']][
            ~data['currency'].isin(CURRENCY_OUT)]
        mess_quant_web = ''
        """
        1、手动对冲
        2、非手动对冲:
            统计头寸超过对冲阈值 coef_stat_threshold >1
            对冲池头寸超过对冲阈值 coef_pool_threshold >1
            未获取价格 rate|U ==0
            对冲状态关闭或者没有状态  对冲状态:非开启
            对冲阈值设置的参数超级小 对冲阈值< 0.00001
            统计行为与对冲池行为不一致  pool_stat < 0 and 价值超错50U
            统计头寸与对冲池差值超过 2500U  pool_stat_u > 2500
            统计对冲头寸价值  df_1['对冲头寸|U'] > THRESHOLD_U
            对冲池头寸价值  df_1['对冲池|U'] > THRESHOLD_U
        """
        dff = df_1[(df_1['currency'].isin(infor.SYMBOLS_HANDLE_HEDGE)) |
                   ((abs(df_1['coef_stat_threshold']) >= COEF) |
                    (abs(df_1['coef_pool_threshold']) >= COEF) |
                    (df_1['rate|U'] == 0) |
                    (df_1['对冲状态'] != True) |
                    (abs(df_1['对冲阈值']) < 0.00001) |
                    ((df_1['pool_stat'] < 0) & (abs(df_1['pool_stat_u']) > 2500)) |
                    (abs(df_1['pool_stat_u']) > POOL_STAT_U) |
                    (abs(df_1['对冲头寸|U']) >= THRESHOLD_U) |
                    (abs(df_1['对冲池|U']) >= THRESHOLD_U)) &
                   (~df_1['currency'].isin(infor.SYMBOLS_HANDLE_HEDGE))]

        if not dff.empty:
            dff = dff.reindex(dff['对冲头寸|U'].abs().sort_values(ascending=True).index)
            mess = ''
            for i in range(len(dff)):
                currency = dff['currency'].iloc[i]
                rate1 = dff['rate|U'].iloc[i]
                round1 = 2 if rate1 > 100000 else 4
                threshold = round(dff['对冲阈值'].iloc[i], 2)
                hedge_stat_side = dff['对冲行为'].iloc[i]
                hedge_stat_amount = round(dff['对冲数量'].iloc[i], round1)
                hedge_stat_amount_u = round(dff['对冲头寸|U'].iloc[i], round1)
                hedge_stat_coef = round(dff['coef_stat_threshold'].iloc[i], 2)
                hedge_pool_status = {False: "对冲关闭"}.get(dff['对冲状态'].iloc[i], '')
                hedge_pool_exchange = dff['对冲交易所'].iloc[i]
                hedge_pool_amount = dff['对冲池'].iloc[i]
                hedge_pool_side = 'SELL' if hedge_pool_amount >= 0 else 'BUY'
                hedge_pool_amount = round(hedge_pool_amount, round1)
                hedge_pool_amount_u = int(dff['对冲池|U'].iloc[i])
                hedge_pool_coef = round(dff['coef_pool_threshold'].iloc[i], 2)
                if currency not in CURRENCY_HANDLE_HEDGE:
                    mess += f"{currency}->阈值: {threshold} {hedge_pool_status} {hedge_pool_exchange}\n" \
                            f"    统计: {hedge_stat_side}:{abs(hedge_stat_amount)} ({hedge_stat_coef}倍，U: {int(hedge_stat_amount_u)})\n" \
                            f"    对冲: {hedge_pool_side}:{abs(hedge_pool_amount)}({hedge_pool_coef}倍，U: {int(hedge_pool_amount_u)})\n"
                    mess_quant_web += f"<b style='color:#FF0000'>{currency}->阈值: {threshold} {hedge_pool_status} {hedge_pool_exchange}</b>[钱包]<br>" \
                                      f"&emsp;统计: {hedge_stat_side}:{abs(hedge_stat_amount)} ({hedge_stat_coef}倍，U: {int(hedge_stat_amount_u)})<br>" \
                                      f"&emsp;对冲: {hedge_pool_side}:{abs(hedge_pool_amount)}({hedge_pool_coef}倍，U: {int(hedge_pool_amount_u)})<br>"

                else:
                    flag = '(需要手动对冲)'
                    if (abs(hedge_stat_amount_u) > HANDLE_AMOUNT_U or abs(hedge_stat_amount) > HANDLE_AMOUNT) and currency in CURRENCY_HANDLE_HEDGE:
                        mess += f"{currency}->阈值: {HANDLE_AMOUNT}U {hedge_pool_status} {hedge_pool_exchange}\n" \
                                f"    统计: {hedge_stat_side}:{hedge_stat_amount} (U: {int(hedge_stat_amount_u)})\n"
                        mess_quant_web += f"<b style='color:#FF0000'>{currency}->阈值: {threshold} {flag}</b>[钱包]<br>" \
                                          f"&emsp;统计: {hedge_stat_side}:{hedge_stat_amount} ({hedge_stat_amount_u}倍，U: {int(hedge_stat_amount_u)})\<br>"

            mess_pool = f'{now_time_dt}(频率5min一次)\n' \
                        f'PS:数量超过阈值的{COEF}倍以上。统计和对冲差距较大，请及时通知相关负责人.\n' \
                        f'{mess}'
            #sendmessage.send_telegram_msg(mess_pool, 'spot_hedge')
            now = datetime.now()
            if now.hour in [0, 8, 16] and now.minute == 0:
                sendmessage.send_telegram_msg(mess_pool, 'spot_hedge')
        print('mess_quant_web', mess_quant_web)
        monitor.get_a_monitor(event_name='threshold', msg=mess_quant_web)

        # # 凌晨盈亏-----------------------------------------------------------------------------------------------
        # 1 获取凌晨盈亏数据
        sql_profit_loss = f"select time,sum(`对冲头寸|U`) as usdt from hedge where time > 'this_condition_start_time'  group by time order by time asc limit 1;"
        re_zone, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_day_start))
        re_month, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_month_start))

        # 累计盈亏
        profit_loss_all = data['对冲头寸|U'].sum()
        # print(f"466行 profit_loss_all: {profit_loss_all}")

        #
        # # 当日盈亏 = 当前盈亏 - 凌晨盈亏 - 昨日有提币今日到账的资金
        # profit_loss_today = cny - re[0][1] - cny_transfer_zero
        aa = 2000 if now_time_dt < '2023-10-14 00:00:00' else 0
        brief = await self.get_profit_loss_brief(this_day_start)
        print('brief', brief)
        profit_loss_today = int(profit_loss_all - re_zone[0][1] - aa - brief)
        profit_loss_month = int(profit_loss_all - re_month[0][1])
        profit_loss_all = int(profit_loss_all)

        mess = f'【现货】{now_time_dt}\n' \
               f'当日盈亏:{profit_loss_today}U\n' \
               f'当月盈亏:{profit_loss_month}U\n' \
               f'累计盈亏:{profit_loss_all}U'
        # sendmessage.send_telegram_msg(mess, 'spot_ProfitLoss')
        # sendmessage.send_telegram_msg(mess, 'spot_contract_profitLoss')
        adj = 0
        return {'time': now_time_dt, 'profit_loss': {'all': f'{profit_loss_all+adj:,}', 'month': f'{profit_loss_month+adj:,}', 'today': f'{profit_loss_today:,}'}}


async def spot_run(rate, hedge_pool, hedge_threshold):
    try:
        t = time.time()
        res = await hedge().get_data_run(rate, hedge_pool, hedge_threshold)
        if HEARTBEAT == 0:
            await heartbeat.i_live_well(server='对冲阈值监控预警', frequency=60 * 60 * 1, index=31)
            return res
        print('历史用时：', time.time() - t)
    except Exception as e:
        mess = f'error：对冲阈值监控预警-->{e} - {traceback.format_exc()}'
        sendmessage.send_telegram_msg(mess, 'Alarm')


async def run():
    rate = await getRateUsdt()
    hedge_threshold = await get_pool_threshold(rate=rate)
    hedge_pool = await get_pool()

    res_wallet = await spot_run(rate, hedge_pool, hedge_threshold)
    res_order = await spot_order(rate, hedge_pool, hedge_threshold)
    adj = 1500
    mess = f"【现货】\n" \
           f"`当日盈亏:{res_wallet['profit_loss']['today'].ljust(8, ' ')} 订单盈亏:{res_order['profit_loss']['today'].ljust(8, ' ')}`\n" \
           f"`当月盈亏:{res_wallet['profit_loss']['month'].ljust(8, ' ')} 订单盈亏:{res_order['profit_loss']['month'].ljust(8, ' ')}`\n" \
           f"`累积盈亏:{res_wallet['profit_loss']['all'].ljust(8, ' ')} 订单盈亏:{res_order['profit_loss']['all'].ljust(8, ' ')}`"
    print(mess)
    # return
    # sendmessage.send_telegram_msg(mess, 'spot_ProfitLoss')
    sendmessage.send_telegram_msg_mdv2(mess, 'spot_ProfitLoss')

    mess_quant_web = mess
    sql = f"insert into spot_contract_pnl (`category`,`wallet`,`order`,`detail`) values ('spot','{res_wallet['profit_loss']['today']}','{res_order['profit_loss']['today']}','{mess_quant_web}')"
    print(sql)
    await G_MysqlSession.insert_sql(sql=sql)
    monitor.get_a_monitor(event_name='profit_loss', msg=mess_quant_web)


async def test():
    now_time = time.time().__int__()
    now_time_dt = get_time.ATime().timestamp_to_timearray(now_time)
    print(type(now_time_dt))
    res = await get_mongo_amount(now_time_dt, {})
    print(res)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
