# coding=utf-8
import loguru
from web3 import Web3
import datetime, json
import requests, time
import asyncio
from pprint import pprint
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_swap
from libs import heartbeat, sendmessage
from libs.database.getredis import get_redis_swap_block_number


NODE_POOL = infor_swap.DEX_NODE_MAPPERS


async def get_blocknumber(link):
    try:
        blocknumber = Web3(Web3.HTTPProvider(link)).eth.block_number
    except Exception as e:
        blocknumber = 0
        loguru.logger.warning(f'error:{link} {e}')
    return blocknumber


async def get_block_number():
    mess, mess_block = '', ''
    error = []
    for chain, node_pools in NODE_POOL.items():
        res = {}
        tasks = []
        for link in node_pools['node_pools']:
            tasks.append([link, asyncio.create_task(get_blocknumber(link))])
        for link, i in tasks:
            m = await i
            if m:
                if m in res:
                    res[m].append(link)
                else:
                    res[m] = [link]
            else:
                error.append(link)
        if not res:
            continue
        amount_min = min(list(res.keys()))
        amount_max = max(list(res.keys()))
        NODE_MONITOR = {}
        if error != []:
            NODE_MONITOR['error'] = error
        NODE_MONITOR['timestamp'] = int(time.time())
        for k, v in res.items():
            NODE_MONITOR[int(amount_max - k)] = v
        await get_redis_swap_block_number.hset('NODE_MONITOR', chain, json.dumps(NODE_MONITOR))
        # NODE_MONITOR = {k: json.dumps(v) for k, v in NODE_MONITOR.items()}
        # rdb.hmset(f'NODE_MONITOR_{url}', NODE_MONITOR)
        # rdb.expire(symbol, 60)

        # 监控存在节点高度差值
        if amount_max - amount_min >= 100:
            mess += f"链:{chain}\n" \
                    f"公共RPC节点个数：{len(node_pools)}\n" \
                    f"节点高度差值:{amount_max - amount_min}\n" \
                    f"区块节点高度-min：{amount_min}\n" \
                    f"地址：{res[amount_min]}\n" \
                    f"区块节点高度-max：{amount_max}\n" \
                    f"地址：{res[amount_max]}\n\n"
            print(mess)
            # res_sort = sorted(res.items(), key=lambda item: item[0])
            # res_sort = {i[0]: i[1] for i in res_sort}
            res_sort = json.dumps(res, sort_keys=True, indent=4, separators=(', ', ': '), ensure_ascii=False)
            mess_block += f"链:{chain}\n" \
                          f"{res_sort}\n"
    if mess:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f'{now}\n！！！紧急情况 马上联系！！！\n可以获取节点高度,但是存在节点高度差\n报警频率5min一次\n' + mess
        sendmessage.send_telegram_msg(message, ser='EmerWarning')
    if error:
        print('error', error)
        message = f'以下节点是没能获取到节点高度的数据，请排查对标的价格是否有异常\n报警频率5min一次\n{error}'
        #sendmessage.send_telegram_msg(message, ser='EmerWarning')
    await heartbeat.i_live_well(server='节点高度监控', frequency=60 * 61, index=31)


async def spot_run():
    try:
        await get_block_number()
        print('ok')
    except Exception as e:
        mess = f'error：节点高度-get_swap_block_number-->{e}'
        sendmessage.send_telegram_msg(mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())
