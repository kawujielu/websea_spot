import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import asyncio
import random
import time
from bson import ObjectId
from scaffold.mongo import G_MongodbSession
import libs
from loguru import logger


redis_db = libs.libs_price_async.redis_db_market_price


async def gen_data():
    type = ['buy', 'sell']
    acc_id = ['99571', '99523', '99526', '99528', '99532', '99533', '99548', '99549', '99551', '99552', '99557',
              '99565',
              '99568', '707366', '707398', '707408', '707420', '707424']
    symbol = await redis_db.async_connection.keys()
    current_symbol = random.choice(symbol)
    price = list((await redis_db.async_connection.hgetall(current_symbol)).values())[0]
    data = {'_id': ObjectId(), 'ts': int(time.time()),
            'symbol': current_symbol, 'price': price,
            'amount': random.randrange(0, 100),
            'taker_user': random.choice(acc_id),
            'maker_user': str(random.randrange(710000, 720000)),
            'taker_order': '', 'maker_order': '', 'type': random.choice(type)}

    current_symbol = random.choice(symbol)
    price = list((await redis_db.async_connection.hgetall(current_symbol)).values())[0]
    data2 = {'_id': ObjectId(), 'ts': int(time.time()),
             'symbol': current_symbol, 'price': price,
             'amount': random.randrange(0, 100),
             'taker_user': str(random.randrange(710000, 720000)),
             'maker_user': random.choice(acc_id),
             'taker_order': '', 'maker_order': '', 'type': random.choice(type)}
    await G_MongodbSession.async_motor_session.insert_one(data)
    logger.info(data)
    await asyncio.sleep(random.randrange(0, 10))
    await G_MongodbSession.async_motor_session.insert_one(data2)
    print(data2)
    await asyncio.sleep(random.randrange(0, 60))


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # for i in range(1, 10000):
    while True:
        loop.run_until_complete(gen_data())
