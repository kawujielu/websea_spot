# coding=utf-8
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, datetime

from config import infor
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
from libs.database.getmongo import G_MongodbSession

# mongodb 获取数据
# "$lt" less than <
# "$gt" greater than >
# "$lte" less than or equal to <=
# "$gte" greater than or equal to >=
# START_TIME =
# END_TIME =
# demand = {'ts': {'$gte': START_TIME, '$lt': END_TIME}}
# mongodb(demand)

acc_id = infor.acc_id
MONGO_START_TIME = G_MongodbSession.MONGO_START_TIME
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
        asset_position, asset_position_volume = await G_MongodbSession.asset_position_process_volume(demand, acc_id)
        valuse = ','.join([f"('{start_zero}','{end_zero}','{k}',{v},{asset_position_volume.get(k, 0)})"
                           for k, v in asset_position.items()])
        if valuse:
            sql = f"insert ignore into mongodb_day (begin_time,end_time,currency,amount,volume_amount) " \
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
        sql = f"select '{MONGO_START_TIME}','{next_zero_dt}',currency,sum(amount),sum(volume_amount) from mongodb_day where end_time<='{next_zero_dt}' group by currency;"
        results, title = await G_MysqlSession.fetch_all(sql=sql)
        if results:
            results = str(results)[1:-1]
            sql = f"insert ignore into mongodb_day_volume (begin_time,end_time,currency,amount,volume_amount) " \
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
        asset_position, asset_position_volume = await G_MongodbSession.asset_position_process_volume(demand, acc_id)
        valuse = ','.join([f"('{startzero_dt}','{today_zero_dt}','{k}',{v},{asset_position_volume.get(k, 0)})"
                           for k, v in asset_position.items()])
        if valuse:
            sql = f"insert ignore into mongodb_day (begin_time,end_time,currency,amount,volume_amount) " \
                  f"values {valuse}"
            await G_MysqlSession.insert_sql(sql=sql)

    except:
        ERROR.append('DAY')
        sendmessage.send_telegram_msg(message='error:get_mongodb_day day', ser='Alarm')

    # 累计前一天数据
    try:
        sql = f"select '{MONGO_START_TIME}','{today_zero_dt}',currency,sum(amount),sum(volume_amount) from mongodb_day where end_time<='{today_zero_dt}' group by currency;"
        results, title = await G_MysqlSession.fetch_all(sql=sql)
        if results:
            results = str(results)[1:-1]
            sql = f"insert ignore into mongodb_day_volume (begin_time,end_time,currency,amount,volume_amount) " \
                  f"values {results}"
            await G_MysqlSession.insert_sql(sql=sql)
    except:
        ERROR.append('VOLUME')
        sendmessage.send_telegram_msg(message='error:get_mongodb_day volume', ser='Alarm')
    if ERROR:
        sendmessage.send_telegram_msg(f"mongodb-spot_day:{ERROR}", ser='Alarm')
        # await heartbeat.i_live_well(server='mongodbDay', frequency=60 * 11, index=60)


async def spot_run_last():
    try:
        await get_mongodb_day_before()
        await get_mongodb_day_volume_before()
    except Exception as e:
        print(f'error:{e}')
        mess = f'error : get_mongdb --> {e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')


async def spot_run():
    try:
        await get_mongodb_day()
        await heartbeat.i_live_well(server='mongodb-spot_day', frequency=60 * 60 * (24 + 12), index=33)
    except Exception as e:
        print(f'error:{e}')
        mess = f'error : get_mongdb --> {e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())
