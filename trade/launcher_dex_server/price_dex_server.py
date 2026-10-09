
# -- 不能注释，此导入为初始化
import initialization
# ---
from ws_libs.price_libs_swap import uniswap_restful
import asyncio
from libs.heartbeat import heart_monitor_async
from many_configs.base_config import ExchangeCode
from libs import (eth_node_pools, bsc_node_pools, heco_node_pools, matic_node_pools,
                  price_dex_price_ex_symbols, recode_msg)


def distribute_node(exchange_name, node_pool_dict):
    node_pool = []
    if exchange_name in [ExchangeCode.sushi.value, ExchangeCode.uniswapv2.value, ExchangeCode.uniswapv3.value]:
        node_pool = eth_node_pools
        pool_name = "1"
    elif exchange_name == ExchangeCode.mdex.value:
        node_pool = heco_node_pools
        pool_name = "2"
    elif exchange_name == ExchangeCode.pancake.value:
        node_pool = bsc_node_pools
        pool_name = "3"

    elif exchange_name == ExchangeCode.matic.value:
        node_pool = matic_node_pools
        pool_name = "4"
    else:
        return None

    num = len(node_pool)

    if pool_name not in node_pool_dict:
        node_pool_dict[pool_name] = {"offset": 0, "pool": node_pool}
    else:
        if node_pool_dict[pool_name]["offset"] < num - 1:
            node_pool_dict[pool_name]["offset"] += 1
        else:
            node_pool_dict[pool_name]["offset"] = 0

    return node_pool[node_pool_dict[pool_name]["offset"]]


async def main():
    tasks = []
    node_pool_dict = {}
    for ex in price_dex_price_ex_symbols:
        for symbol in price_dex_price_ex_symbols[ex]:
            node = distribute_node(ex, node_pool_dict)
            if not node:
                await recode_msg.recode_error_msg(f"{ex} 没有配置可用节点", "send_telegram_important_msg_url")
            tasks.append(asyncio.create_task(uniswap_restful(symbol, node, ex, monitor=f"价格服务_去中心化|{ex}")))

    tasks.append(asyncio.create_task(heart_monitor_async()))
    for i in tasks:
        await i

if __name__ == '__main__':
    asyncio.run(main())
