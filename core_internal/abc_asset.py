import asyncio
import traceback
import datetime, time
from bson import ObjectId
from datetime import timedelta
from libs.recode_msg import recode_error_msg
from libs.feature_utils import get_currency_exposure
from scaffold.mongo import G_MongodbSession
from scaffold.mysql import Hedge_MysqlSession
from many_configs import global_variable
from many_configs.account_config import ABC_ACCOUNTS
import loguru


class AbcAssetPosition:
    def __init__(self):
        self.last_cur_utc = datetime.datetime.strptime('2022-02-20 00:00:00', "%Y-%m-%d %H:%M:%S")

    async def init_position(self):
        sql = "SELECT coin,amount,generation_time_utc, avg_price from abc_asset_gap ;"
        res = await Hedge_MysqlSession.fetch_all(sql)
        if res:
            self.last_cur_utc = max([i[2] for i in res])
            for i in res:
                global_variable.ABC_POSITIONS[i[0]] = i[1]
                if i[3]:
                    global_variable.ABC_POSITIONS_AVG_PRICE[i[0]] = i[3]
        loguru.logger.info("abc_asset_init_position -- ok")

    async def asset_position_process(self, demand):
        """
            统计ABC货币缺口
        """
        loguru.logger.info(f'asset_position_process {demand=}')
        async for re in G_MongodbSession.async_motor_session.find(demand):
            try:
                loguru.logger.info(f'asset_position_process {re = }')
                currency_base, currency_quote = re['symbol'].split('-')
                # type 表示 fromUser 的行为
                if (re['fromUser'] in ABC_ACCOUNTS and re['type'] == 'sell') or (
                        re['toUser'] in ABC_ACCOUNTS and re['type'] == 'buy'):
                    currency_base_amount = float(re['amount']) * (-1)
                    currency_quote_amount = float(re['amount']) * float(re['price'])

                    # global_variable.ABC_POSITIONS[currency_base] = global_variable.ABC_POSITIONS.get(currency_base,
                    #                                                                                 0) + float(
                    #     re['amount']) * (-1)
                    # global_variable.ABC_POSITIONS[currency_quote] = global_variable.ABC_POSITIONS.get(currency_quote,
                    #                                                                                  0) + float(
                    #     re['amount']) * float(re['price'])

                elif (re['fromUser'] in ABC_ACCOUNTS and re['type'] == 'buy') or (
                        re['toUser'] in ABC_ACCOUNTS and re['type'] == 'sell'):
                    currency_base_amount = float(re['amount'])
                    currency_quote_amount = float(re['amount']) * float(re['price']) * (-1)
                    # global_variable.ABC_POSITIONS[currency_base] = global_variable.ABC_POSITIONS. \
                    #                                                   get(currency_base, 0) + float(re['amount'])
                    # global_variable.ABC_POSITIONS[currency_quote] = global_variable.ABC_POSITIONS. \
                    #                                                    get(currency_quote, 0) + \
                    #                                                float(re['amount']) * float(re['price']) * (-1)
                else:
                    # msg = f"asset_position_process_data {re['symbol']=} {re['fromUser']=} {re['type']=} {re['toUser']=}"
                    # loguru.logger.error(msg)
                    # await recode_error_msg(msg, server="spot_hedge")
                    continue
                # TODO 因为只有一个交易区USDT，所以只考虑了quote是USDT的情况，如果有其他交易区，需要同时考虑quote为其他币种的均价计算
                cur_position_avg = global_variable.ABC_POSITIONS_AVG_PRICE.get(currency_base, 0)
                cur_position = await get_currency_exposure(currency_base)
                if cur_position_avg and cur_position:
                    new_position = cur_position + currency_base_amount
                else:
                    new_position = currency_base_amount
                new_position_avg = (cur_position_avg * cur_position + float(re['price']) * currency_base_amount) / new_position if new_position else None
                loguru.logger.info(f"asset_position_process_avg {currency_base} {cur_position_avg=} {cur_position=} {new_position=} {new_position_avg=}")
                if new_position_avg:
                    global_variable.ABC_POSITIONS_AVG_PRICE[currency_base] = new_position_avg

                global_variable.ABC_POSITIONS[currency_base] = global_variable.ABC_POSITIONS.get(currency_base, 0) + currency_base_amount
                global_variable.ABC_POSITIONS[currency_quote] = global_variable.ABC_POSITIONS.get(currency_quote, 0) + currency_quote_amount
                loguru.logger.info(f'ABC_POSITIONS {global_variable.ABC_POSITIONS}')
            except:
                msg = f'asset_position_process:mongo_order has error'
                await recode_error_msg(msg, server="spot_hedge")
                loguru.logger.info(msg)

    async def asset_position_process_avg_price(self, symbol, amount):

        end_time = int(time.time())
        start_time = int(end_time - 60 * 60 * 2)
        start_oid = ObjectId.from_datetime(datetime.datetime.utcfromtimestamp(start_time))
        end_oid = ObjectId.from_datetime(datetime.datetime.utcfromtimestamp(end_time))
        demand = {"_id": {"$gt": start_oid, "$lte": end_oid}, 'symbol': symbol}
        side = "SELL" if amount > 0 else "BUY"
        base_amount = 0
        quote_amount = 0

        # side 是对冲方向，和量化的方向是反的
        # 对冲 sell  -5 +20 +10 = 25  =   外部 +  用户  =  外部 - 量化
        # 量化 buy


        # 下面都是量化行为
        #  9：30  buy 10 、
        #  9：20  buy 20 、
        #  8：00 sell 5 【降序】
        #  ｜｜｜｜｜  初始头寸 ：0 外部没有头寸 ：0

        loguru.logger.info(f'asset_position_process {demand=}')
        async for re in G_MongodbSession.async_motor_session.find(demand).sort('ts', -1):
            try:
                loguru.logger.info(f'asset_position_process {re = }')

                if (side == 'BUY' and ((re['fromUser'] in ABC_ACCOUNTS and re['type'] == 'sell') or (re['toUser'] in ABC_ACCOUNTS and re['type'] == 'buy'))) or (
                        side == 'SELL' and ((re['fromUser'] in ABC_ACCOUNTS and re['type'] == 'buy') or (re['toUser'] in ABC_ACCOUNTS and re['type'] == 'sell'))):
                    base_amount += float(re['amount'])
                    quote_amount += float(re['amount']) * float(re['price'])
                    if base_amount > abs(amount):
                        break
                else:
                    break
            except:
                loguru.logger.info(f'error:mongo_order {re}')
        return quote_amount / base_amount if base_amount else None

    async def asset_position_collector(self):
        start_oid = ObjectId.from_datetime(self.last_cur_utc)  # 查询起始点
        cur_utc = datetime.datetime.utcfromtimestamp(int(time.time()))
        generation_time = cur_utc - timedelta(seconds=2)
        end_oid = ObjectId.from_datetime(generation_time)  # 查询终止点
        demand = {"_id": {"$gt": start_oid, "$lte": end_oid}}
        # start_oid = int(time.time()) - 10 * 60
        # end_oid = int(time.time())
        # demand = {"ts": {"$gt": start_oid, "$lte": end_oid}}
        loguru.logger.info(f'asset_position_collector_time,{self.last_cur_utc=} {generation_time= }')
        await self.asset_position_process(demand)
        # 保存到数据库中
        loguru.logger.info(f'ABC_POSITIONS, {global_variable.ABC_POSITIONS}')
        if global_variable.ABC_POSITIONS:
            values_list = []
            for k, v in global_variable.ABC_POSITIONS.items():
                avg_price = global_variable.ABC_POSITIONS_AVG_PRICE.get(k, 0)
                values_list.append(str((k, v, str(generation_time), avg_price)))
            values = ','.join(values_list)
            sql = f'INSERT ignore INTO abc_asset_gap(coin,amount,generation_time_utc, avg_price) VALUES {values} on duplicate key update amount = values(amount),generation_time_utc = values(generation_time_utc),avg_price = values(avg_price)'
            await Hedge_MysqlSession.insert(sql)
            # TODO 如果有报错的怎么知道
            sql_all = f'INSERT ignore INTO abc_asset_gap_all(coin,amount,generation_time_utc, avg_price) VALUES {values}'
            await Hedge_MysqlSession.insert(sql_all)
            self.last_cur_utc = generation_time

    async def run(self):
        while True:
            try:
                if not global_variable.ABC_POSITIONS:
                    await self.init_position()
                await self.asset_position_collector()
                loguru.logger.info(f'AbcAssetPosition running -- {global_variable.ABC_POSITIONS}')
                await asyncio.sleep(8)
            except Exception:
                msg = f"abc asset position_collector {traceback.format_exc()}"
                loguru.logger.info(f'{msg}')
                await recode_error_msg(msg, server="spot_hedge")
                await asyncio.sleep(10)


abc_asset_position_instance = AbcAssetPosition()

if __name__ == '__main__':
    asyncio.run(abc_asset_position_instance.asset_position_process_avg_price(symbol='ETH-USDT', amount=3.45))
