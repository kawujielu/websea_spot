import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import json
from libs import heartbeat, libs_price_async
from exchanges.restful_api.abc_spot import AApi
from exchanges.restful_api.abc_contract import AbcApi
import asyncio
import traceback

redis_db = libs_price_async.redis_db_control
websea_instance = AApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
contract_instance = AbcApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
heart = {}


async def get_precision():
    for i in [1, 2, 3]:
        try:
            precision = await websea_instance.precision()
            if precision['errno'] == 0:
                result = dict(precision['result'])
                price = result['BTC-USDT']['price']
                break
            else:
                print('spot', precision)
        except Exception as e:
            print(f'spot precision error: {traceback.format_exc()}')
        await asyncio.sleep(5)
    return result


async def get_contract_precision():
    for i in [1, 2, 3]:
        try:
            precision = await contract_instance.precision()
            if precision['errno'] == 0:
                result = dict(precision['result'])
                price = result['BTC-USDT']['price']
                break
            else:
                print('contract', precision)
        except Exception as e:
            print(f'contract precision error: {traceback.format_exc()}')
        await asyncio.sleep(5)
    return result


async def write_redis_precision(name='redis_precision'):
    precision_dict = await get_precision()
    precision = {k: json.dumps(v) for k, v in precision_dict.items()}
    flag = await redis_db.async_connection.hmset(name, precision)
    print('现货精度设置', flag)
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f'{cu_time} ==> 正式环境现货精度更新结束' + '=' * 100)
    cu_time = int(time.time())
    heart['spot'] = cu_time


async def write_contract_redis_precision(name='contract_redis_precision'):
    precision_dict = await get_contract_precision()
    precision = {k: json.dumps(v) for k, v in precision_dict.items()}
    flag = await redis_db.async_connection.hmset(name, precision)
    print('合约精度设置', flag)
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f'{cu_time} ==> 正式环境合约精度更新结束' + '=' * 100)
    cu_time = int(time.time())
    heart['contract'] = cu_time


async def send_heart():
    monitor = ['spot', 'contract']
    cu_time = int(time.time())
    error_msg = []
    for k, v in heart.items():
        if cu_time - int(v) > 60 * 12:
            error_msg.append(k)
    for info in monitor:
        if info not in list(heart.keys()):
            error_msg.append(info)
    if error_msg:
        await heartbeat.i_live_not_well(error_msg, "redis精度", 60 * 12, 66)
    else:
        await heartbeat.i_live_well("redis精度", 60 * 12, 66)


async def main():
    await write_redis_precision()
    await write_contract_redis_precision()
    await send_heart()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
