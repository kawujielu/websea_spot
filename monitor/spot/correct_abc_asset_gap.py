# coding=utf-8
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, infor_contract
from libs import sendmessage, get_time
from libs.database.getmongo import G_MongodbSession, G_MongodbSession_CON
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession
from spot.spot_setting import getRate, getRateUsdt, get_mongo_amount

import asyncio, datetime, time
from bson.objectid import ObjectId
from datetime import datetime
from spot.spot_get_mongo_wallet import hedge
from loguru import logger

acc_id = infor.acc_id
REDUCE_U = 1
d = {'BSSB': 2, 'MULTI': 0, 'JENNER': -12608.36, 'JENSOL': 12608.36, 'ZK': -333.9}
atime = get_time.ATime()


async def run1():
    Hedge = hedge()
    start_time_dt = Hedge.start_time_dt

    today_time, today_time_dt = Hedge.today_zero()
    now_time = time.time().__int__()

    # abc_asset_gap
    sql = "select coin,amount,generation_time_utc from abc_asset_gap"
    abc_asset_gap, title = await Hedge_MysqlSession.fetch_all(sql=sql)
    generation_time_utc = max([i[2] for i in abc_asset_gap])
    generation_time_utc = str(generation_time_utc)
    generation_time_utc_time = atime.timearray_to_timestamp(generation_time_utc) + 8 * 60 * 60

    abc_asset_gap = {i[0]: i[1] for i in abc_asset_gap}
    start_time = atime.timearray_to_timestamp(start_time_dt)

    # demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(today_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(now_time))}}
    demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(start_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(generation_time_utc_time))}}
    asset_position = await G_MongodbSession.asset_position_process(demand=demand, acc_id=acc_id)

    # # 获取每日的数据
    # sql = f"select distinct currency,amount from mongodb_day_volume where begin_time ='{start_time_dt}' and end_time='{today_time_dt}';"
    # results, title = await G_MysqlSession.fetch_all(sql)
    # mongo = {i[0]: i[1] for i in results}
    # print(mongo)
    mongo = {}

    coins = set(abc_asset_gap.keys()) | set(mongo.keys()) | set(asset_position.keys())
    rate = await getRateUsdt(infor.SYMBOLS_PAIR)
    msg = ""
    for s in coins:

        coin_mongo_amount = mongo.get(s, 0) + asset_position.get(s, 0)
        coin_abc_asset_gap_amount = abc_asset_gap.get(s, 0)
        price = rate.get(s, 0)
        reduce = coin_mongo_amount - coin_abc_asset_gap_amount
        reduce_u = abs(coin_mongo_amount - coin_abc_asset_gap_amount) * price
        if reduce_u > REDUCE_U or price == 0:
            msg += f"【{s}】\n差值 :{reduce}\n差值|U :{int(reduce_u)}U\nmongo :{coin_mongo_amount}\nhedge_abc :{coin_abc_asset_gap_amount}\n\n"
    if msg:
        mess = f"连续报警处于一个稳定的差值，建议矫正数据(1h/次)\nabs(mongo数据 - 对冲统计abc)>{REDUCE_U}U\n\n" + msg
        # sendmessage.send_telegram_msg(message=mess, ser='mongo_and_abc')


async def diff_mongo_gap(rate):
    Hedge = hedge()
    start_time_dt = Hedge.start_time_dt
    today_time, today_time_dt = Hedge.today_zero()
    now_time = time.time().__int__()
    if abs(now_time - today_time) < 5 * 10:
        return

    # abc_asset_gap
    sql = "select coin,amount,generation_time_utc from abc_asset_gap"
    abc_asset_gap, title = await Hedge_MysqlSession.fetch_all(sql=sql)
    generation_time_utc = max([i[2] for i in abc_asset_gap])
    generation_time_utc = str(generation_time_utc)
    abc_asset_gap = {i[0]: i[1] for i in abc_asset_gap}

    generation_time_utc_time = atime.timearray_to_timestamp(generation_time_utc) + 8 * 60 * 60
    # demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(today_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(now_time))}}
    demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(today_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(generation_time_utc_time))}}
    asset_position = await G_MongodbSession.asset_position_process(demand=demand, acc_id=acc_id)
    # print(asset_position)

    # # 获取每日的数据
    # sql = f"select distinct currency,amount from mongodb_day_volume where begin_time ='{start_time_dt}' and end_time='{today_time_dt}';"
    # results, title = await G_MysqlSession.fetch_all(sql)
    # mongo = {i[0]: i[1] for i in results}
    # print(mongo)
    today_time_dt = atime.timestamp_to_timearray(now_time)

    mongo, asset_position = await get_mongo_amount(today_time_dt, asset_position)
    coins = set(abc_asset_gap.keys()) | set(mongo.keys()) | set(asset_position.keys())
    # rate = await getRateUsdt(infor.SYMBOLS_PAIR)

    msg = ""
    for s in coins:
        if s in d.keys():
            continue
        coin_mongo_amount = mongo.get(s, 0) + asset_position.get(s, 0)
        coin_abc_asset_gap_amount = abc_asset_gap.get(s, 0)
        price = rate.get(s, 0)
        reduce = round(coin_mongo_amount - coin_abc_asset_gap_amount, 4)
        reduce_u = abs(reduce) * price
        if reduce_u > REDUCE_U or (price == 0 and reduce != 0):
            msg += f"【{s}】\n差值 :{reduce}\n差值|U :{int(reduce_u)}U\nmongo :{coin_mongo_amount}\nhedge_abc :{coin_abc_asset_gap_amount}\n\n"
    if msg:
        mess = f"连续报警处于一个稳定的差值，建议矫正数据(1h/次)\nabs(mongo数据 - 对冲统计abc)>{REDUCE_U}U\n\n" + msg
        print(mess)
        # sendmessage.send_telegram_msg(message=mess, ser='mongo_and_abc')


async def diff_mongo_orders(rate):
    end_time = int(time.time() - 10 * 60)
    start_time = end_time - 60 * 60 * 1

    start_time_dt = atime.timestamp_to_timearray(start_time)
    end_time_dt = atime.timestamp_to_timearray(end_time)
    sql = f"select symbol,sum(amount) amount,sum(amountQuote) amountQuote from mongoorders where ts >= '{start_time_dt}' and ts < '{end_time_dt}' group by symbol"
    res, title = await G_MysqlSession.fetch_all(sql)

    res_coin = {}
    for i in res:
        base, quote = i[0].split('-')
        res_coin[base] = float(i[1]) + float(res_coin.get(base, 0))
        res_coin[quote] = float(i[2]) + float(res_coin.get(quote, 0))

    demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(start_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(end_time))}}
    # demand = {'ts': {'$gte': start_time, '$lt': end_time}}
    asset_position = await G_MongodbSession.asset_position_process(demand=demand, acc_id=acc_id, asset_position={})
    coins = set(asset_position.keys()) | set(res_coin.keys())
    # print('asset_position', asset_position)
    # print('res_coin', res_coin)
    logger.info(f"现货 - mongo : {asset_position}")
    logger.info(f"现货 - mysql : {res_coin}")
    msg = ""
    for s in coins:
        reduce = asset_position.get(s, 0) - res_coin.get(s, 0)
        price = rate.get(s, 0)
        reduce_u = abs(reduce) * price
        if reduce_u > REDUCE_U or price == 0:
            msg += f"【{s}】\n差值 :{reduce}\n差值|U :{int(reduce_u)}U\nmongo :{asset_position.get(s, 0)}\norder :{res_coin.get(s, 0)}\n\n"
    if msg:
        mess = f"【现货】转存数据存在异常，需要及时处理(1h/次)\nabs(mongo数据 - 订单统计)>{REDUCE_U}U\n{end_time_dt} - {start_time_dt}\n\n" + msg
        # sendmessage.send_telegram_msg(message=mess, ser='mongo_and_abc')
        print(mess)


async def diff_mongo_orders_con():
    ids = infor_contract.acc_id_contract
    end_time = int(time.time() - 10 * 60)
    start_time = end_time - 60 * 60 * 1

    start_time_dt = atime.timestamp_to_timearray(start_time)
    end_time_dt = atime.timestamp_to_timearray(end_time)
    sql = f"select symbol,type,sum(amount) amount from contract_mongoorders where ts >= '{start_time_dt}' and ts < '{end_time_dt}' and user_id not in {tuple(ids)} group by symbol,type"
    res, title = await G_MysqlSession.fetch_all(sql)

    res_coin = {}
    for i in res:
        symbol, side, amount = i
        if not res_coin.get(symbol):
            res_coin[symbol] = {}
        res_coin[symbol][side] = amount

    demand = {'_id': {'$gte': ObjectId.from_datetime(datetime.utcfromtimestamp(start_time)), '$lt': ObjectId.from_datetime(datetime.utcfromtimestamp(end_time))}}
    # demand = {'ts': {'$gte': start_time, '$lt': end_time}}
    asset_position = await G_MongodbSession_CON.asset_position_demand_orders(demand=demand)

    orders = []
    SIDE = {'1': '开多', '2': '开空', '3': '平多', '4': '平空', }
    for i in asset_position:
        symbol = i['symbol']
        amount = float(i['amount'])
        takerUser = i['takerUser']
        makerUser = i['makerUser']
        takerBuyOrSell = SIDE[i['takerBuyOrSell']]
        makerBuyOrSell = SIDE[i['makerBuyOrSell']]
        if takerUser not in ids:
            orders.append([symbol, takerBuyOrSell, amount])
        if makerUser not in ids:
            orders.append([symbol, makerBuyOrSell, amount])
    ord = {}
    for i in orders:
        symbol, side, amount = i
        if not ord.get(symbol):
            ord[symbol] = {}
        ord[symbol][side] = amount + ord[symbol].get(side, 0)

    symbols = set(ord.keys()) | set(res_coin.keys())
    logger.info(f"合约 - mongo : {ord}")
    logger.info(f"合约 - mysql : {res_coin}")

    msg = ""
    for s in symbols:
        a = ord.get(s, {})
        b = res_coin.get(s, {})

        if a != b:
            msg += f"【{s}】\n" \
                   f"mongo :{a}\n" \
                   f"order :{b}\n\n"
    if msg:
        mess = f"【合约】转存数据存在异常，需要及时处理(1h/次)\n{end_time_dt} - {start_time_dt}\n\n" + msg
        # sendmessage.send_telegram_msg(message=mess, ser='mongo_and_abc')
        print(mess)


async def run():
    rate = await getRateUsdt(infor.SYMBOLS_PAIR)
    await diff_mongo_gap(rate)
    await diff_mongo_orders(rate)
    await diff_mongo_orders_con()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
