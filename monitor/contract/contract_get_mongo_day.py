# coding=utf-8
import asyncio
import loguru
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, datetime

from config import infor_contract
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
from libs.database.getmongo import G_MongodbSession_CON

acc_id = infor_contract.acc_id_contract
MONGO_START_TIME = G_MongodbSession_CON.MONGO_START_TIME
NUM_DAY = 1000


# 实践戳转化为时间格式
def timestamp_to_timearray(timestamp):
    # 转换为localtime
    time_local = time.localtime(timestamp)
    # 转换为新的时间格式
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
    return dt
    # 时间格式转化为时间戳


def timearray_to_timestamp(dt):
    # 转换为时间数组
    timeArray = time.strptime(dt, "%Y-%m-%d %H:%M:%S")
    # 转换为时间戳
    timestamp = time.mktime(timeArray).__int__()
    return timestamp


async def get_mongo_demand(demand):
    asset_position = {}
    orders = await G_MongodbSession_CON.asset_position_demand_orders(demand)
    for re in orders:
        symbol = re['symbol']
        if not asset_position.get(symbol):
            asset_position[symbol] = 0

        if re['takerUser'] not in acc_id:
            asset_position[symbol] += float(re['takerProfitLoss']) if re['takerProfitLoss'] else 0
        if re['makerUser'] not in acc_id:
            asset_position[symbol] += float(re['makerProfitLoss']) if re['makerProfitLoss'] else 0
    return asset_position


async def get_mongodb_day_before():
    today_zero_dt = datetime.datetime.now().date()
    today_zero = int(time.mktime(today_zero_dt.timetuple()))
    startzero = timearray_to_timestamp(MONGO_START_TIME)

    for i in range(1, NUM_DAY):
        end_zero_time = today_zero - i * 3600 * 24
        start_zero_time = today_zero - (i + 1) * 3600 * 24
        start_zero = timestamp_to_timearray(start_zero_time)
        end_zero = timestamp_to_timearray(end_zero_time)
        print(i, start_zero_time, end_zero_time, start_zero, end_zero)

        if end_zero_time < startzero:
            break
        demand = {'ts': {'$gte': start_zero_time, '$lt': end_zero_time}}
        asset_position = await get_mongo_demand(demand)
        valuse = ','.join([f"('{start_zero}','{end_zero}','{k}',{v})"
                           for k, v in asset_position.items()])
        if valuse:
            sql = f"insert ignore into contract_mongodb_day (begin_time,end_time,symbol,profitloss) " \
                  f"values {valuse}"
            await G_MysqlSession.insert_sql(sql=sql)


async def get_mongodb_day_volume_before():
    today_zero_dt = datetime.datetime.now().date()
    today_zero = int(time.mktime(today_zero_dt.timetuple()))
    startzero = timearray_to_timestamp(MONGO_START_TIME)

    for i in range(1, NUM_DAY):
        next_zero = startzero + (i) * 60 * 60 * 24
        next_zero_dt = timestamp_to_timearray(next_zero)
        if next_zero > today_zero:
            print('break', startzero, next_zero)
            break
        print(i, next_zero, today_zero, startzero, next_zero_dt)
        sql = f"select '{MONGO_START_TIME}','{next_zero_dt}',symbol,sum(profitloss) from contract_mongodb_day where end_time<='{next_zero_dt}' group by symbol;"
        results, title = await G_MysqlSession.fetch_all(sql=sql)
        if results:
            results = str(results)[1:-1]
            sql = f"insert ignore into contract_mongodb_day_volume (begin_time,end_time,symbol,profitloss) " \
                  f"values {results}"
            await G_MysqlSession.insert_sql(sql=sql)


async def get_mongodb_day():
    today_zero_dt = datetime.datetime.now().date()
    today_zero = int(time.mktime(today_zero_dt.timetuple()))
    startzero = int(today_zero - 24 * 60 * 60)
    startzero_dt = timestamp_to_timearray(startzero)
    today_zero_dt = timestamp_to_timearray(today_zero)
    print(startzero, startzero_dt, today_zero_dt)
    ERROR = []
    # 前一天数据
    try:
        demand = {'ts': {'$gte': startzero, '$lt': today_zero}}
        asset_position = await get_mongo_demand(demand)
        valuse = ','.join([f"('{startzero_dt}','{today_zero_dt}','{k}',{v})"
                           for k, v in asset_position.items()])
        if valuse:
            sql = f"insert ignore into contract_mongodb_day (begin_time,end_time,symbol,profitloss) " \
                  f"values {valuse}"
            await G_MysqlSession.insert_sql(sql=sql)

    except:
        ERROR.append('DAY')
        sendmessage.send_telegram_msg(message='error:get_contract_mongodb_day day', ser='Alarm')

    # 累计前一天数据
    try:
        sql = f"select '{MONGO_START_TIME}','{today_zero_dt}',symbol,sum(profitloss) from contract_mongodb_day where end_time<='{today_zero_dt}' group by symbol;"
        results, title = await G_MysqlSession.fetch_all(sql=sql)
        if results:
            results = str(results)[1:-1]
            sql = f"insert ignore into contract_mongodb_day_volume (begin_time,end_time,symbol,profitloss) " \
                  f"values {results}"
            await G_MysqlSession.insert_sql(sql=sql)
    except:
        ERROR.append('VOLUME')
        sendmessage.send_telegram_msg(message='error:get_contract_mongodb_day volume', ser='Alarm')
    if ERROR:
        sendmessage.send_telegram_msg(f"mongodb-contract_day:{ERROR}", ser='Alarm')
        # await heartbeat.i_live_well(server='mongodbDay', frequency=60 * 11, index=60)


async def contract_run_last():
    try:
        await get_mongodb_day_before()
        await get_mongodb_day_volume_before()
    except Exception as e:
        print(f'error:{e}')
        mess = f'error : get_ontract_mongdb --> {e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')


async def contract_run():
    try:
        await get_mongodb_day()
        await heartbeat.i_live_well(server='mongodb-contract_day', frequency=60 * 60 * (24 + 12), index=33)
    except Exception as e:
        print(f'error:{e}')
        mess = f'error : get_ontract_mongdb --> {e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(contract_run())
