import datetime, time
from bson import ObjectId
from datetime import timedelta
import loguru
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from libs.database.getmysql import G_MysqlSession
from config.infor_load import DEBUG
import traceback

acc_id = []
if DEBUG:
    spot_mongodb_url = 'mongodb://root:0dtNu0Np5noFEFPy@172.20.0.10:27018'
    contract_mongodb_url = 'mongodb://root:0dtNu0Np5noFEFPy@172.18.40.113:27020/'
else:
    spot_mongodb_url = 'mongodb://spot-ro:PcwDn46F24MHGjRa@10.60.99.86:27018/'
    contract_mongodb_url = "mongodb://future-ro:qVy8HB31R5Wc7fHU@10.60.99.85:27020/"  # 'mongodb://root:GD0wBplOGwxQTaUI@10.0.96.71:27020/'


class MongodbSession:

    def __init__(self, _mongodb_url="", table='real_deal'):
        self.client = None
        self._mongodb_url = _mongodb_url
        self.table = table

    @property
    def async_motor_session(self):
        if self.client is None:
            self.client = AsyncIOMotorClient(self._mongodb_url)['exchange'][self.table]

        return self.client


class AbcPosition:
    # MONGO_START_TIME = datetime.datetime.strptime('2023-01-01 00:00:00', "%Y-%m-%d %H:%M:%S")
    MONGO_START_TIME = '2023-06-01 00:00:00'

    def __init__(self, MongodbSession):
        self.MongodbSession = MongodbSession

    async def asset_position_process(self, demand, acc_id, asset_position={}):
        async for re in self.MongodbSession.async_motor_session.find(demand):
            try:
                base, quote = re['symbol'].split('-')

                if (re['fromUser'] in acc_id and re['toUser'] not in acc_id) or (
                        re['fromUser'] not in acc_id and re['toUser'] in acc_id):
                    # if (re['taker_user'] in acc_id and re['type'] == 'sell') or (
                    #         re['maker_user'] in acc_id and re['type'] == 'buy'):
                    if (re['fromUser'] in acc_id and re['type'] == 'sell') or (
                            re['toUser'] in acc_id and re['type'] == 'buy'):
                        asset_position[base] = asset_position.get(base, 0) + float(re['amount']) * (-1)
                        asset_position[quote] = asset_position.get(quote, 0) + \
                                                float(re['amount']) * float(re['price'])

                    # elif (re['taker_user'] in acc_id and re['type'] == 'buy') or (
                    #         re['maker_user'] in acc_id and re['type'] == 'sell'):
                    elif (re['fromUser'] in acc_id and re['type'] == 'buy') or (
                            re['toUser'] in acc_id and re['type'] == 'sell'):

                        asset_position[base] = asset_position.get(base, 0) + float(re['amount'])
                        asset_position[quote] = asset_position.get(quote, 0) + \
                                                float(re['amount']) * float(re['price']) * (-1)
            except:
                loguru.logger.info(f'error:mongo_order {re}')
        return asset_position

    async def asset_position_process_volume(self, demand, acc_id):
        asset_position = {}
        asset_position_volume = {}
        async for re in self.MongodbSession.async_motor_session.find(demand):
            try:
                base, quote = re['symbol'].split('-')

                if (re['fromUser'] in acc_id and re['toUser'] not in acc_id) or (
                        re['fromUser'] not in acc_id and re['toUser'] in acc_id):
                    # if 1:
                    # if (re['taker_user'] in acc_id and re['type'] == 'sell') or (
                    #         re['maker_user'] in acc_id and re['type'] == 'buy'):
                    if (re['fromUser'] in acc_id and re['type'] == 'sell') or (
                            re['toUser'] in acc_id and re['type'] == 'buy'):

                        asset_position[base] = asset_position.get(base, 0) + float(re['amount']) * (-1)
                        asset_position[quote] = asset_position.get(quote, 0) + float(re['amount']) * float(re['price'])
                    # elif (re['taker_user'] in acc_id and re['type'] == 'buy') or (
                    #         re['maker_user'] in acc_id and re['type'] == 'sell'):
                    elif (re['fromUser'] in acc_id and re['type'] == 'buy') or (
                            re['toUser'] in acc_id and re['type'] == 'sell'):

                        asset_position[base] = asset_position.get(base, 0) + float(re['amount'])
                        asset_position[quote] = asset_position.get(quote, 0) + float(re['amount']) * float(re['price']) * (-1)

                asset_position_volume[base] = asset_position_volume.get(base, 0) + float(re['amount'])
                asset_position_volume[quote] = asset_position_volume.get(quote, 0) + float(re['amount'])
            except:
                loguru.logger.info(f'error:mongo_order {re}')
        return asset_position, asset_position_volume

    async def asset_position_orders(self, demand, acc_id, spotfee_userid=None):
        # 用户角度：uid:123
        # symbol：BTC-USDT
        # amount : 2
        # amountBase：-40000
        # side：buy
        # amount 为正是买，为负是

        orders = []
        orders_user = []
        async for re in self.MongodbSession.async_motor_session.find(demand):
            try:
                T = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(re['ts']))
                symbol = re['symbol']
                object_id = str(re['_id'])
                price = float(re['price'])
                amount = float(re['amount'])
                amountQuote = float(re['amount']) * float(re['price'])
                side = re['type']
                coef = -1 if re['type'] == 'buy' else 1
                fromFee = float(re['fromFee'])
                fromQuoteFee = fromFee if side == 'sell' else fromFee * price
                toFee = float(re['toFee'])
                toQuoteFee = toFee if side == 'buy' else toFee * price

                if re['fromUser'] in acc_id and re['toUser'] not in acc_id:
                    orders.append(
                        [object_id, T, re['toUser'], re['toOrder'], symbol, {'sell': 'buy', 'buy': 'sell'}[side], amount * (-1) * coef, price,
                         amountQuote * coef, re['fromUser'], toFee, toQuoteFee])
                elif re['toUser'] in acc_id and re['fromUser'] not in acc_id:
                    orders.append(
                        [object_id, T, re['fromUser'], re['fromOrder'], symbol, side, amount * coef,
                         price, amountQuote * (-1) * coef, re['toUser'], fromFee, fromQuoteFee])
                elif re['toUser'] not in acc_id and re['fromUser'] not in acc_id:
                    if (re['fromUser'] in spotfee_userid and re['toUser'] not in spotfee_userid) or \
                            (re['fromUser'] not in spotfee_userid and re['toUser'] in spotfee_userid):
                        fromUserType = "交易" if re['fromUser'] in spotfee_userid else "普通"
                        toUserType = "交易" if re['toUser'] in spotfee_userid else "普通"
                        orders_user.append(
                            [object_id, T, re['toUser'], re['toOrder'], symbol, {'sell': 'buy', 'buy': 'sell'}[side], amount * (-1) * coef, price,
                             amountQuote * coef, fromUserType, toFee, toQuoteFee])
                        orders_user.append(
                            [object_id, T, re['fromUser'], re['fromOrder'], symbol, side, amount * coef,
                             price, amountQuote * (-1) * coef, toUserType, fromFee, fromQuoteFee])

                # if re['taker_user'] in acc_id and re['maker_user'] not in acc_id:
                #     orders.append(
                #         [object_id, T, re['maker_user'], re['maker_order'], symbol, side, amount * coef, price,
                #          amountQuote * (-1) * coef, re['taker_user']])
                # elif re['maker_user'] in acc_id and re['taker_user'] not in acc_id:
                #     orders.append(
                #         [object_id, T, re['taker_user'], re['taker_order'], symbol, side, amount * (-1) * coef,
                #          price, amountQuote * coef, re['maker_user']])
            except:
                loguru.logger.info(f'error:mongo_order {re} {traceback.format_exc()}')
        if orders_user:
            values = ','.join([str(tuple(i)) for i in orders_user])
            sql = f"insert ignore into mongoorders_user (`_id`,ts,id,`order`,symbol,side, amount, price,amountQuote,userType,fee,feeQuote) " \
                  f"values {values}"
            await G_MysqlSession.insert_sql(sql)

        if orders:
            values = ','.join([str(tuple(i)) for i in orders])
            sql = f"insert ignore into mongoorders (`_id`,ts,id,`order`,symbol,side, amount, price,amountQuote,Aid,fee,feeQuote) " \
                  f"values {values}"
            await G_MysqlSession.insert_sql(sql)

            return orders

    async def asset_position_orders_contract(self, demand):
        # 1开多 2开空 3平多 4 平空
        """
            create table mongoorders(
            -- `index` int not null auto_increment,
            `_id`  varchar(48) not null ,
            id int(10) ,
            symbol varchar(20),
            ts datetime,
            amount double,
            price double,
            amountQuote double,
            primary key (`_id`,id,symbol,ts)
            );
            :return:
            """
        orders = []
        async for re in self.MongodbSession.async_motor_session.find(demand):
            print(re)
            try:
                side = {'1': '开多', '2': '开空', '3': '平多', '4': '平空', }
                OrderSource = {1: '普通', 2: '爆仓', 3: '止盈', 4: '止损', 5: '反手', 6: '限价止盈止损触发', }
                T = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(re['ts']))
                symbol = re['symbol']
                object_id = str(re['_id'])
                dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(re['ts']))
                price = float(re['price'])
                amount = float(re['amount'])  # 张数
                takerUser = re['takerUser']
                makerUser = re['makerUser']
                takerOrder = re['takerOrder']
                makerOrder = re['makerOrder']
                takerFee = float(re['takerFee'])
                makerFee = float(re['makerFee'])
                takerIsFull = True if re['takerIsFull'] == 1 else False
                makerIsFull = True if re['makerIsFull'] == 1 else False
                takerBuyOrSell = side.get(re['takerBuyOrSell'], re['takerBuyOrSell'])
                makerBuyOrSell = side.get(re['makerBuyOrSell'], re['makerBuyOrSell'])
                takerOpenAvgPrice = float(re['takerOpenAvgPrice'])
                makerOpenAvgPrice = float(re['makerOpenAvgPrice'])
                takerProfitLoss = float(re['takerProfitLoss'])
                makerProfitLoss = float(re['makerProfitLoss'])
                takerFaceValue = float(re['takerFaceValue'])  # 面值
                makerFaceValue = float(re['makerFaceValue'])
                takerMultiple = float(re['takerMultiple'])
                makerMultiple = float(re['makerMultiple'])

                takerOrderSource = OrderSource.get(re['takerOrderSource'], re['takerOrderSource'])
                makerOrderSource = OrderSource.get(re['makerOrderSource'], re['makerOrderSource'])

                taker = [object_id, dt, symbol, takerOrder, takerUser, takerIsFull, takerMultiple, takerBuyOrSell, amount, price, takerFee, takerOpenAvgPrice, takerProfitLoss, takerFaceValue, takerOrderSource]
                maker = [object_id, dt, symbol, makerOrder, makerUser, makerIsFull, makerMultiple, makerBuyOrSell, amount, price, makerFee, makerOpenAvgPrice, makerProfitLoss, makerFaceValue, makerOrderSource]
                orders.append(taker)
                orders.append(maker)

            except:
                loguru.logger.info(f'error:mongo_order {re}')
        if orders:
            values = ','.join([str(tuple(i)) for i in orders])
            sql = f"insert ignore into contract_mongoorders (`_id`,ts,symbol,`order`, user_id, isfull,multiple,`type`, amount, price, fee, openavgprice, profitLoss, facevalue,ordersource) " \
                  f"values {values}"
            await G_MysqlSession.insert_sql(sql)

            return orders

    async def asset_position_collector(self, acc_id):
        start_oid = ObjectId.from_datetime(self.MONGO_START_TIME)  # 查询起始点
        cur_utc = datetime.datetime.utcfromtimestamp(int(time.time()))
        generation_time = cur_utc - timedelta(seconds=10)
        end_oid = ObjectId.from_datetime(generation_time)  # 查询终止点
        demand = {"_id": {"$gt": start_oid, "$lte": end_oid}}
        print(self.MONGO_START_TIME, cur_utc)
        await self.asset_position_process(demand, acc_id)
        # 保存到数据库中
        # if global_variable.ABC_POSITIONS:
        #     values = ','.join([str((k, v)) for k, v in global_variable.ABC_POSITIONS.items()])
        #     sql = f'INSERT INTO abc_asset_gap(coin,amount) VALUES {values} on duplicate key update amount = values(amount)'
        #     await Hedge_MysqlSession.insert(sql)
        #     sql_all = f'INSERT INTO abc_asset_gap_all(coin,amount) VALUES {values}'
        #     await Hedge_MysqlSession.insert(sql_all)
        #     self.last_cur_utc = generation_time

    async def asset_position_demand_orders(self, demand):
        orders = []
        async for re in self.MongodbSession.async_motor_session.find(demand):
            try:
                orders.append(re)
            except:
                loguru.logger.info(f'error:mongo_order {re}')
        return orders


G_MongodbSession = AbcPosition(MongodbSession(spot_mongodb_url, table='real_deal'))
G_MongodbSession_CON = AbcPosition(MongodbSession(contract_mongodb_url, table='real_contract_deal'))

if __name__ == '__main__':
    print(DEBUG)
    print(spot_mongodb_url)
    end = int(time.time())
    demand = {'ts': {'$gte': 1718035200, '$lt': 1718121600}}
    spot_id = ['10', '11', '12', '13', '14', '15', '16', '17']
    # mm = asyncio.run(G_MongodbSession.asset_position_orders(demand, acc_id=spot_id, spotfee_userid=[]))
    mm = asyncio.run(G_MongodbSession_CON.asset_position_orders_contract(demand))
    # mm = asyncio.run(G_MongodbSession.asset_position_process(demand,acc_id=[2]))
    print(mm)
