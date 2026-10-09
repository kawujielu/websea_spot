from threading import Thread
import urllib3
import traceback
import time
from many_configs import global_variable
import asyncio
from libs import libs_config, decorator
from libs.heartbeat import heart_monitor
from libs.senddd import send_telegram
from datetime import datetime
from ws_libs.volume_trade_add_contract import risk_control
from ws_libs.ws_abc_contract_depth import async_abc_contract_ask_bid_price_ws
from many_configs.contract_currency_config import contract_all_symbols
from urllib3.exceptions import InsecureRequestWarning

trade_thread_list = []

urllib3.disable_warnings(InsecureRequestWarning)

DEFAULT_MAX_CONTRACT = 20000

MAX_CONTRACT_MAPPER = {s: int(global_variable.SYMBOLS_CONTRACT_CONDITION[s]["maxQuantity"]) for s in global_variable.SYMBOLS_CONTRACT_CONDITION}


async def contract_order_task(s, a, long_account, short_account):
    p, _, _ = await risk_control(s)
    order_tasks = [long_account.contract_add(s, "sell-limit", a, p, "close"),
                   short_account.contract_add(s, "buy-limit", a, p, "close")]
    dones, pendings = await asyncio.wait(order_tasks)


from abcapi_plus import AbcApi

contract_close_accounts_long = AbcApi(token="", secret_key="", )
contract_close_accounts_short = AbcApi(token="", secret_key="", )


@decorator.monitor_handler
def position_close():
    while True:
        contract_detail = {}
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = asyncio.get_event_loop()
        tasks = []
        try:
            symbol = "NEAR-USDT"
            amount = 4900
            tasks.append(asyncio.ensure_future(
                contract_order_task(symbol, amount, contract_close_accounts_long, contract_close_accounts_short)))
            if tasks:
                loop.run_until_complete(asyncio.wait(tasks))

        except BaseException as e:
            error_msg = "close" + traceback.format_exc()
            print(datetime.now(), error_msg)
            send_telegram(f"{e}\n{error_msg}", "contract_close", libs_config.DEBUG)

        time.sleep(1)


trade_thread_list.append(Thread(target=position_close, args=(), kwargs={"monitor": "合约_平仓|"}))
trade_thread_list.append(Thread(target=asyncio.run, args=(async_abc_contract_ask_bid_price_ws(contract_all_symbols),)))
trade_thread_list.append(Thread(target=heart_monitor, args=()))


for t in trade_thread_list:
    t.start()

for t in trade_thread_list:
    t.join()
