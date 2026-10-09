# coding=utf-8
import pandas as pd
import json, collections, datetime, time
from bson.objectid import ObjectId
from datetime import datetime, timedelta, date
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, infor_hedge, monitor, infor_swap, infor_load
from libs import heartbeat, sendmessage, get_time
from libs.database.getmongo import G_MongodbSession
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession
from spot.spot_exchange_deposit_withdraw_fee import get_fee_asset_gap
from spot.spot_setting import get_mongo_amount

getTime = get_time.ATime()
# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = infor.acc_id
SYMBOL = []
SYMBOLS_LIST = list(set(infor.SYMBOLS_LIST + SYMBOL))

CURRENCY_OUT = [s.plint('-')[0] for s in infor.SYMBOLS_OUT + SYMBOL] + ['USDT']
CURRENCY_HANDLE_HEDGE = [s.plint('-')[0] for s in infor.SYMBOLS_HANDLE_HEDGE + SYMBOL] + ['USDT']
COEF = 1.2
# 统计对冲头寸与对冲池头寸差值
POOL_STAT_U = 2500
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

    def __init__(self):
        self.start_time_dt = '2023-06-01 00:00:00'
        # self.start_time_dt = '2023-08-29 00:00:00'
        self.start_time = getTime.timearray_to_timestamp(self.start_time_dt)
        pass

    async def get_trades_orders(self, start_time, end_time):
        sql = f"SELECT currency,symbol,side,SUM(amount) amount,SUM(price*amount)amountQuote,feecoin,SUM(fee),exchange from trades where time >= '{start_time}' and  time < '{end_time}' GROUP BY currency,symbol,side,feecoin,exchange"
        res, title = await Hedge_MysqlSession.fetch_all(sql=sql)
        result = {}
        spec_symbol_rate_mapping = infor_load.spec_symbol_rate_mapping
        if spec_symbol_rate_mapping.get('gateio'):
            spec_symbol_rate_mapping['gate'] = spec_symbol_rate_mapping.pop('gateio')

        if res:
            for i in res:
                currency = i[0]
                ex = i[7]
                symbol = i[1]
                symbol, pr = spec_symbol_rate_mapping.get(ex, {}).get(symbol, [symbol, 1])
                base, quote = symbol.split('-')
                side = i[2].upper() == 'BUY'
                amount = i[3] if side else i[3] * (-1)
                amountQuote = i[4] * (-1) if side else i[4]
                fee = i[6]
                feecoin = i[5]

                if base == currency:
                    amount = amount * pr
                if quote == currency:
                    amountQuote = amountQuote * pr
                if feecoin == currency:
                    fee = fee * pr

                result[base] = {'amount': result.get(base, {}).get('amount', 0) + amount,
                                'volume_amount': result.get(base, {}).get('volume_amount', 0) + abs(amount)
                                }
                result[quote] = {'amount': result.get(quote, {}).get('amount', 0) + amountQuote,
                                 'volume_amount': result.get(quote, {}).get('volume_amount', 0) + abs(amountQuote)
                                 }
                result[feecoin] = {'amount': result.get(feecoin, {}).get('amount', 0) - fee,
                                   'volume_amount': result.get(feecoin, {}).get('volume_amount', 0) + fee
                                   }

        return result

    async def get_trades_orders_day(self, start_time, end_time):
        result = await self.get_trades_orders(start_time, end_time)
        if result:
            results = ",".join([f"('{start_time}','{end_time}','{k}',{v['amount']},{v['volume_amount']})" for k, v in result.items()])
            sql = f"insert ignore into trades_orders_day (begin_time,end_time,currency,amount,volume_amount) " \
                  f"values {results}"
            await G_MysqlSession.insert_sql(sql=sql)
        vol_res, title1 = await G_MysqlSession.fetch_all(sql=f"SELECT currency,SUM(amount) amount,SUM(volume_amount) volume_amount from trades_orders_day where end_time<='{end_time}' GROUP BY currency")
        if vol_res:
            vol_res = ",".join([f"('{self.start_time_dt}','{end_time}','{i[0]}',{i[1]},{i[2]})" for i in vol_res])
            sql = f"insert ignore into trades_orders_day_volume (begin_time,end_time,currency,amount,volume_amount) " \
                  f"values {vol_res}"
            await G_MysqlSession.insert_sql(sql=sql)

    async def get_trades_orders_before(self):
        for i in range(10000):
            start_time = self.start_time + 60 * 60 * 24 * i
            end_time = start_time + 60 * 60 * 24
            start_time_dt = getTime.timestamp_to_timearray(start_time)
            end_time_dt = getTime.timestamp_to_timearray(end_time)
            print(i, start_time_dt, end_time_dt)
            if end_time > time.time():
                break
            await self.get_trades_orders_day(start_time_dt, end_time_dt)

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

    async def get_data_run(self, rate, hedge_pool, hedge_threshold):
        # ----------------------------------------------------------------------------------------------------
        this_month_start, this_day_start = self.get_monthstart_daystart()
        today_time, today_time_dt = self.today_zero()

        if int(time.time()) - today_time < 10 * 60:
            end_time_dt = today_time_dt
            start_time_dt = getTime.timestamp_to_timearray(int(today_time - 60 * 60 * 24))
            await self.get_trades_orders_day(start_time_dt, end_time_dt)
            today_time, today_time_dt = self.today_zero()
            # sys.exit()

        now_time = time.time().__int__()
        now_time_dt = get_time.ATime().timestamp_to_timearray(now_time)

        # mongo ----------------------------------------------------------------------------------------------------
        demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(today_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(now_time))}}
        asset_position = await G_MongodbSession.asset_position_process(demand=demand, acc_id=acc_id, asset_position={})

        # # 获取每日的数据
        # sql = f"select distinct currency,amount from mongodb_day_volume where begin_time ='{self.start_time_dt}' and end_time='{today_time_dt}';"
        # results, title = await G_MysqlSession.fetch_all(sql)
        # mongo = {i[0]: i[1] for i in results}

        mongo, asset_position = await get_mongo_amount(now_time_dt, asset_position)

        # # 外部订单 ----------------------------------------------------------------------------------------------------
        # results_trades_order, title_trades_order = await G_MysqlSession.fetch_all(sql=f"select distinct currency,amount from trades_orders_day_volume where begin_time ='{self.start_time_dt}' and end_time='{today_time_dt}';")
        # trades_orders_history = {i[0]: i[1] for i in results_trades_order}
        trades_orders = await self.get_trades_orders(start_time=today_time_dt, end_time=now_time_dt)
        trades_orders = {s: v['amount'] for s, v in trades_orders.items()}
        trades_orders_history, trades_orders = await get_mongo_amount(now_time_dt, trades_orders, type='ex_orders')

        # 充提手续费 ----------------------------------------------------------------------------------------------------
        start_time_fee, asset_gap = await get_fee_asset_gap()
        temps = []

        for k in SYMBOLS_LIST:
            temp = collections.OrderedDict()
            temp['time'] = now_time_dt
            temp['currency'] = k
            temp['abc'] = mongo.get(k, 0) + asset_position.get(k, 0)
            # temp['ex'] = trades_orders.get(k, {}).get('amount', 0) + trades_orders_history.get(k, 0)
            temp['ex'] = trades_orders.get(k, 0) + trades_orders_history.get(k, 0)
            temp['fee'] = asset_gap.get(k, 0)
            rate_u = rate.get(k, 0)
            temp['rate|U'] = rate_u
            temp['对冲头寸'] = temp['abc'] + temp['ex'] + temp['fee']
            temp['对冲头寸|U'] = temp['对冲头寸'] * rate_u
            temp['对冲行为'] = 'SELL' if temp['对冲头寸'] > 0 else 'BUY' if temp['对冲头寸'] < 0 else '-'
            temp['对冲数量'] = abs(temp['对冲头寸'])
            # 参考—对冲阈值
            threshold = hedge_threshold.get(k, {})
            temp['对冲阈值'] = threshold['threshold'] if threshold.get('threshold', 0) else 10000 / rate_u if rate_u else 10000
            temp['对冲池'] = hedge_pool.get(k, 0)
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
        sql = f"insert into hedge_trades_orders ({title_sql}) values {values} ;"

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
            统计行为与对冲池行为不一致  pool_stat < 0
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
                    ((df_1['pool_stat'] < 0) & (abs(df_1['pool_stat_u']) > 100)) |
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
                    mess_quant_web += f"<b style='color:#FF0000'>{currency}->阈值: {threshold} {hedge_pool_status} {hedge_pool_exchange}</b>[订单]<br>" \
                                      f"&emsp;统计: {hedge_stat_side}:{abs(hedge_stat_amount)} ({hedge_stat_coef}倍，U: {int(hedge_stat_amount_u)})<br>" \
                                      f"&emsp;对冲: {hedge_pool_side}:{abs(hedge_pool_amount)}({hedge_pool_coef}倍，U: {int(hedge_pool_amount_u)})<br>"

                else:
                    flag = '(需要手动对冲)'
                    if (abs(hedge_stat_amount_u) > HANDLE_AMOUNT_U or abs(hedge_stat_amount) > HANDLE_AMOUNT) and currency in currency:
                        mess += f"{currency}->阈值: {HANDLE_AMOUNT}U {hedge_pool_status} {hedge_pool_exchange}\n" \
                                f"    统计: {hedge_stat_side}:{hedge_stat_amount} (U: {int(hedge_stat_amount_u)})\n"
                        mess_quant_web += f"<b style='color:#FF0000'>{currency}->阈值: {threshold} {flag}</b>[订单]<br>" \
                                          f"&emsp;统计: {hedge_stat_side}:{hedge_stat_amount} ({hedge_stat_amount_u}倍，U: {int(hedge_stat_amount_u)})\<br>"

            mess_pool = f'{now_time_dt}(频率5min一次)[订单统计方式]\n' \
                        f'PS:数量超过阈值的{COEF}倍以上。统计和对冲差距较大，请及时通知相关负责人.\n' \
                        f'{mess}'
            # 如果有报警，仅在每天的 0:00、8:00、16:00 整点（分钟为0）才发送一次
            now = datetime.now()
            if now.hour in [0, 8, 16] and now.minute == 0:
                sendmessage.send_telegram_msg(mess_pool, 'spot_hedge')
        monitor.get_a_monitor(event_name='threshold_order', msg=mess_quant_web)

        # # 凌晨盈亏-----------------------------------------------------------------------------------------------
        # 1 获取凌晨盈亏数据
        sql_profit_loss = f"select time,sum(`对冲头寸|U`) as usdt from hedge_trades_orders where time > 'this_condition_start_time'  group by time order by time asc limit 1;"
        re_zone, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_day_start))
        re_month, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_month_start))

        # 累计盈亏
        profit_loss_all = data['对冲头寸|U'].sum()

        profit_loss_today = int(profit_loss_all - re_zone[0][1])
        profit_loss_month = int(profit_loss_all - re_month[0][1])
        profit_loss_all = int(profit_loss_all)

        mess = f'【现货】\nmongo与外部交易所,订单统计方式\n{now_time_dt}\n' \
               f'当日盈亏:{profit_loss_today}U\n' \
               f'当月盈亏:{profit_loss_month}U\n' \
               f'累计盈亏:{profit_loss_all}U'
        print(mess)
        # sendmessage.send_telegram_msg(mess, 'spot_ProfitLoss')
        adj = 0

        return {'time': now_time_dt, 'profit_loss': {'all': f'{profit_loss_all+adj:,}', 'month': f'{profit_loss_month+adj:,}', 'today': f'{profit_loss_today:,}'}}


async def spot_run(rate, hedge_pool, hedge_threshold):
    try:
        t = time.time()
        res = await hedge().get_data_run(rate, hedge_pool, hedge_threshold)
        await heartbeat.i_live_well(server='对冲阈值监控预警|订单', frequency=60 * 60 * 1, index=31)
        print('历史用时：', time.time() - t)
        return res
    except Exception as e:
        mess = f'error：对冲阈值监控预警|订单-->{e}'
        sendmessage.send_telegram_msg(mess, 'Alarm')


async def test():
    now_time = time.time().__int__()
    now_time_dt = get_time.ATime().timestamp_to_timearray(now_time)
    print(type(now_time_dt))
    res = await get_mongo_amount(now_time_dt, {}, type='ex_orders')
    print(res)


if __name__ == '__main__':
    pass
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(hedeg().get_trades_orders_before())
