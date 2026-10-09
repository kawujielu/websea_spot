# -- 不能注释，此导入为初始化
import initialization
# ---
import urllib3
import traceback
import time
from many_configs.abc_config import contract_close_accounts
from many_configs import global_variable
import asyncio
from libs import libs_config, decorator, recode_msg, libs_account
from libs.heartbeat import i_live_transit_station, heart_monitor_async
from libs.senddd import send_telegram
from datetime import datetime
from ws_libs.volume_trade_add_contract import risk_control
from ws_libs.ws_abc_contract_depth import async_abc_contract_ask_bid_price_ws
from loguru import logger

CUR_MAIN_SERVER = "平仓服务"

DEFAULT_MAX_CONTRACT = 20000
EXCEPT_POSITION = 100000

MAX_CONTRACT_MAPPER = {s: int(global_variable.SYMBOLS_CONTRACT_CONDITION[s]["maxQuantity"]) for s in global_variable.SYMBOLS_CONTRACT_CONDITION}


async def contract_order_task(s, a, long_account, short_account):
    p, _, _ = await risk_control(s)
    order_tasks = [asyncio.create_task(long_account.contract_add(s, "sell-limit", a, p, "close")),
                   asyncio.create_task(short_account.contract_add(s, "buy-limit", a, p, "close"))]
    await asyncio.wait(order_tasks)

close_time_per = 5

@decorator.monitor_handler
async def position_close(contract_accounts):
    i_live_transit_station("main_instance", frequency=10)
    while True:
        contract_detail = {}
        order_tasks = []
        has_except = []
        try:
            for account in contract_accounts:
                cur_token = account._token_
                s_start = time.time()
                res = await account.contract_position()
                if not cur_token:
                    continue
                diff_time = time.time() - s_start
                # print(cur_token, "position_close_position_time", diff_time)
                if diff_time > 3:
                    has_except.append(f"合约平仓服务：持仓接口超时 {diff_time} s")
                positions = res.get("result", [])
                # print(cur_token, "positions", res)
                for position in positions:
                    symbol = position["symbol"]
                    position_type = position["type"]
                    position_amount = int(float(position["avail_amount"]))
                    if cur_token == libs_account["contract_volume"]["token"]:
                        position_amount = position_amount * 0.5
                    if symbol not in contract_detail:
                        contract_detail[symbol] = {"long": [], "short": []}
                    # if position_amount > EXCEPT_POSITION:
                    #     has_except.append(f"{symbol}-{position_amount}张")

                    if position_type == 2:  # 空仓
                        contract_detail[symbol]["short"].append((account, position_amount))
                    elif position_type == 1:  # 多仓
                        contract_detail[symbol]["long"].append((account, position_amount))

            for symbol in contract_detail:
                long = contract_detail[symbol]["long"]
                short = contract_detail[symbol]["short"]
                sorted_long = sorted(long, key=lambda x: x[1], reverse=True)
                sorted_short = sorted(short, key=lambda x: x[1], reverse=True)
                # if sorted_long:
                #     print(datetime.now(), "sorted_long", symbol, sorted_long[0][0]._token_, sorted_long[0][1], sorted_long)
                # else:
                #     print(datetime.now(), "sorted_long", sorted_long)
                #
                # if sorted_short:
                #     print(datetime.now(), "sorted_short", symbol, sorted_short[0][0]._token_, sorted_short[0][1], sorted_short)
                # else:
                #     print(datetime.now(), "sorted_short", symbol, sorted_short)

                pair_length = min(len(sorted_long), len(sorted_short))
                for length in range(pair_length):
                    min_amount = min(min(sorted_long[length][1], sorted_short[length][1]),
                                     MAX_CONTRACT_MAPPER.get(symbol, DEFAULT_MAX_CONTRACT))
                    if min_amount < 1000:
                        continue
                    amount = min_amount * float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])

                    order_tasks.append(asyncio.create_task(
                        contract_order_task(symbol, amount, sorted_long[length][0], sorted_short[length][0])))
            if order_tasks:
                await asyncio.wait(order_tasks)
            if has_except:
                has_except_msg = ", ".join(has_except)
                has_except_msg = f"平仓服务：\n {has_except_msg}"
                await recode_msg.recode_error_msg(has_except_msg, 'send_telegram_important_msg_url')

            i_live_transit_station("main_instance", frequency=close_time_per+2)
        except BaseException as e:
            error_msg = f"contract-close-error {traceback.format_exc()}"
            logger.error(error_msg)
            await recode_msg.recode_error_msg(f"平仓服务执行异常", "send_telegram_important_msg_url")
        await asyncio.sleep(5)


async def main():
    tasks = [asyncio.create_task(position_close(contract_close_accounts, monitor=f"{CUR_MAIN_SERVER}_执行|USDT")),
             # asyncio.create_task(async_abc_contract_ask_bid_price_ws(CONTRACT_SUPPORT_SYMBOLS,
             #                                                           monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|合约")),
             asyncio.create_task(heart_monitor_async())]

    for t in tasks:
        await t


if __name__ == '__main__':
    asyncio.run(main())
