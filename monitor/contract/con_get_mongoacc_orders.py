# coding=utf-8
import pandas as pd
import datetime, time, asyncio
from datetime import timedelta
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmongo import G_MongodbSession_CON, G_MysqlSession
from libs import get_time, heartbeat, sendmessage
from bson.objectid import ObjectId
from config import infor_contract

acc_id = infor_contract.acc_id_contract


# 用户的行为 正数 buy 负数 sell
async def get_mongodb_order(START_TIME, END_TIME):
    if type(START_TIME) == ObjectId:
        str_oid = START_TIME
    elif len(str(START_TIME)) == 24:
        str_oid = ObjectId(START_TIME)
    else:
        str_oid = ObjectId.from_datetime(datetime.datetime.utcfromtimestamp(START_TIME))  # 起点时间终止点
    if not END_TIME:
        end_oid = ObjectId.from_datetime(datetime.datetime.utcfromtimestamp(int(time.time())) - timedelta(seconds=10))
    else:
        end_oid = ObjectId.from_datetime(datetime.datetime.utcfromtimestamp(END_TIME))  # 终点时间
    demand = {'_id': {'$gte': str_oid, '$lt': end_oid}}
    logger.info(f'{demand} {end_oid} {type(end_oid)}')
    print(demand)
    orders = await G_MongodbSession_CON.asset_position_orders_contract(demand)
    end_oid  = max([i[0] for i in orders]) if orders else str_oid
    return end_oid


async def get_orders():
    sql = "select max(`_id`) from contract_mongoorders;"
    results, title = await G_MysqlSession.fetch_all(sql=sql)

    now_time = time.time()
    DAY = 7
    START_TIME1 = 0
    if results[0][0]:
        objectid = results[0][0]
        start_time_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(objectid[:8], 16)))
        logger.info(f'START_TIME_dt:{start_time_dt} {objectid} {type(start_time_dt)} {type(objectid)}')
        START_TIME = get_time.ATime().timearray_to_timestamp(start_time_dt)
        if int(time.time()) > (60 * 60 * 24 * 1 + START_TIME):
            START_TIME1 = START_TIME
        else:
            end_oid = objectid

    else:
        logger.info('订单数据库中没有数据,获取前7天数据')
        START_TIME1 = int(now_time - 60 * 60 * 24 * DAY)

    if START_TIME1:
        for i in range(DAY):
            START_TIME = int(START_TIME1 + 60 * 60 * 24 * i)
            END_TIME = int(START_TIME + 60 * 60 * 24)

            if END_TIME < now_time:
                logger.info(
                    f'{i}天 {get_time.ATime().timestamp_to_timearray(START_TIME)} {get_time.ATime().timestamp_to_timearray(END_TIME)}')
                end_oid = await get_mongodb_order(START_TIME, END_TIME, )

    return end_oid


async def contract_run():
    SLEEP_TIME = 60 * 5
    # 初始化数据 获取前7天数据
    end_oid = await get_orders()
    await asyncio.sleep(10)
    while True:
        try:
            end_oid = await get_mongodb_order(START_TIME=end_oid, END_TIME='', )
            await heartbeat.i_live_well(server='合约订单明细', frequency=60 * 31, index=11)
            print('ok')
            await asyncio.sleep(SLEEP_TIME)
        except Exception as e:
            mess = f'error：get_mongoacc_orders contract-->{e}'
            sendmessage.send_telegram_msg(message=mess, ser='Alarm')
            await asyncio.sleep(SLEEP_TIME / 2)


if __name__ == "__main__":
    asyncio.run(contract_run())
