import ujson
import time

from libs.m_aiohttp import G_RequestSession
from libs import libs_price_async
import asyncio
import traceback
from many_configs.contract_currency_config import FOLLOW_EXCHANGE_ORDER_REVERSE, FOLLOW_EXCHANGE_FUNDING_RATE_SPEC, \
    contract_symbols, contract_price_ex_symbols
from many_configs import global_variable
from libs.heartbeat import i_live_transit_station
from libs import decorator
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs.base_config import ExchangeCode
from many_configs.contract_currency_config import contract_price_trans_symbols, contract_price_trans_symbols_from_contract
from loguru import logger
from libs import recode_msg


headers = {
    'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

FUNDING_RATE_EXCHANGES = {}
MSG_CONTROL = {}


async def funding_rate_strategy(f, s):
    """
    当外部资金费率较小时，我们跟随，
    当外部资金费率较大时，减幅跟随，这样保证我们的合约价格更贴近指数价格，避免因为资金费率延迟价差波动，导致在资金结算时可能的大幅度的跳跃
    我们使用资金费率控制合约价格和指数价格的价差是有延迟的
    """
    f = float(f)
    if f == 0:
        return f
    sign = f / abs(f)
    max_funding_rate = 0.007
    if abs(f) > max_funding_rate:
        n = time.time()
        if n - MSG_CONTROL.get(s, 0) > 60 * 60 * 2:
            await recode_msg.recode_error_msg(f"{s}合约交易对资金费率达到{f}（1小时报告一次）", 'fund_rate')
            MSG_CONTROL[s] = n
    if "PERP-USDT" in s:
        if abs(f) < 0.001:
            return f
        else:
            return sign * min(max(0.0006, abs(f) / 2.0), max_funding_rate + 0.001)
    elif "BTC-USDT" in s:
        return sign * min(0.0006, abs(f) / 3.0)
    else:
        if abs(f) < 0.0006:
            return f
        else:
            return sign * min(max(0.0006, abs(f) / 2.0), max_funding_rate)


class BinanceApi:
    cur_ex = ExchangeCode.bn.value

    async def funding_rate(self):
        bn_url = f"{EXCHANGE_CONFIG[self.cur_ex]['contract_restful']}/fapi/v1/premiumIndex"
        async with G_RequestSession.request.get(bn_url, headers=headers) as r:
            res = await r.text()
            res = ujson.loads(res)
            res = {r["symbol"]: r["lastFundingRate"] for r in res}
            # print(res)
            usdt_busd_zone_list = []

            for s, f in res.items():
                ex_symbol = ""
                if "USDT" in s:
                    ex_symbol = s.replace("USDT", "-USDT")
                # 如果没有usdt区对应的交易对，那么退而求其次选用busd区的对标
                elif "BUSD" in s and s.replace("BUSD", "USDT") not in res:
                    ex_symbol = s.replace("BUSD", "-USDT")
                if ex_symbol:
                    abc_symbol = contract_price_trans_symbols.get(self.cur_ex, {}).get(ex_symbol)
                    if not abc_symbol:
                        abc_symbol = contract_price_trans_symbols_from_contract.get(self.cur_ex, {}).get(ex_symbol)

                    if abc_symbol:
                        s = f"{self.cur_ex}-{abc_symbol}"
                        ex_symbol_funding = {"symbol": abc_symbol, "funding_rate": await funding_rate_strategy(f, s)}
                        usdt_busd_zone_list.append(ex_symbol_funding)
            FUNDING_RATE_EXCHANGES[self.cur_ex] = usdt_busd_zone_list


class HuobiApi:
    cur_ex = ExchangeCode.hb.value

    async def funding_rate(self):
        hb_url = f"{EXCHANGE_CONFIG[self.cur_ex]['contract_restful']}/linear-swap-api/v1/swap_batch_funding_rate"
        async with G_RequestSession.request.get(hb_url, headers=headers) as r:
            res = await r.text()
            res = ujson.loads(res)
            res = {r["contract_code"]: r["funding_rate"] for r in res["data"]}
            usdt_busd_zone_list = []
            for s, f in res.items():
                ex_symbol = ""
                if "USDT" in s:
                    ex_symbol = s
                # 如果没有usdt区对应的交易对，那么退而求其次选用husd区的对标
                elif "HUSD" in s and s.replace("HUSD", "USDT") not in res:
                    ex_symbol = s.replace("HUSD", "USDT")
                if ex_symbol:
                    abc_symbol = contract_price_trans_symbols.get(self.cur_ex, {}).get(ex_symbol)
                    if not abc_symbol:
                        abc_symbol = contract_price_trans_symbols_from_contract.get(self.cur_ex, {}).get(ex_symbol)

                    if abc_symbol:
                        s = f"{self.cur_ex}-{abc_symbol}"
                        ex_symbol_funding = {"symbol": abc_symbol, "funding_rate": await funding_rate_strategy(f, s)}
                        usdt_busd_zone_list.append(ex_symbol_funding)
            FUNDING_RATE_EXCHANGES[self.cur_ex] = usdt_busd_zone_list


class OkexApi:
    cur_ex = ExchangeCode.okex.value

    async def funding_rate(self):
        usdt_busd_zone_list = []
        # tasks = [asyncio.create_task(self.fund_rate(symbol, usdt_busd_zone_list)) for symbol in contract_symbols]
        # await asyncio.wait(tasks)
        if self.cur_ex in contract_price_ex_symbols:
            for symbol in contract_price_ex_symbols[self.cur_ex]:
                await self.fund_rate(symbol, usdt_busd_zone_list)
                await asyncio.sleep(0.2)

        FUNDING_RATE_EXCHANGES[self.cur_ex] = usdt_busd_zone_list

    async def fund_rate(self, ex_symbol, usdt_busd_zone_list):
        ok_url = f"{EXCHANGE_CONFIG[self.cur_ex]['contract_restful']}/api/v5/public/funding-rate?instId={ex_symbol}-SWAP"
        try:
            async with G_RequestSession.request.get(ok_url, headers=headers) as r:
                res = await r.text()
                res = ujson.loads(res)
                if res['code'] == '0':
                    abc_symbol = contract_price_trans_symbols.get(self.cur_ex, {}).get(ex_symbol)
                    if not abc_symbol:
                        abc_symbol = contract_price_trans_symbols_from_contract.get(self.cur_ex, {}).get(ex_symbol)

                    if abc_symbol:
                        f = res['data'][0]["fundingRate"]
                        s = f"{self.cur_ex}-{abc_symbol}"
                        ex_symbol_funding = {"symbol": abc_symbol, "funding_rate": await funding_rate_strategy(f, s)}
                        usdt_busd_zone_list.append(ex_symbol_funding)
        except BaseException as e:
            print('error', e)


@decorator.monitor_handler
# 定时更新资金费率的主流程
async def funding_rate_fetch():
    except_none_symbols = ["DODO-USDT", "GROK-USDT", ]
    i_live_transit_station("main_instance", frequency=120)
    [i_live_transit_station("item_instance", f"{symbol}", frequency=60) for symbol in contract_symbols if symbol not in except_none_symbols]

    fetch_timeout = 30
    while True:
        exchanges = [BinanceApi(), OkexApi(), HuobiApi()]
        try:
            tasks = [asyncio.create_task(ex.funding_rate()) for ex in exchanges]

            await asyncio.wait(tasks)
            for ex in FOLLOW_EXCHANGE_ORDER_REVERSE:
                if ex not in FUNDING_RATE_EXCHANGES:
                    continue
                symbols_info = FUNDING_RATE_EXCHANGES[ex]
                for symbol_info in symbols_info:
                    symbol = symbol_info["symbol"]
                    funding_rate = symbol_info["funding_rate"]
                    if symbol not in contract_symbols:
                        continue
                    if FOLLOW_EXCHANGE_FUNDING_RATE_SPEC.get(symbol) is None:
                        global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE[symbol] = funding_rate
                    elif ex == FOLLOW_EXCHANGE_FUNDING_RATE_SPEC.get(symbol):
                        global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE[symbol] = funding_rate
                    i_live_transit_station("item_instance", f"{symbol}", frequency=120)
                    i_live_transit_station("item_instance", "KAS-USDT", frequency=120)
            # logger.info(f"{global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE}")

            await libs_price_async.redis_db_control.async_connection.hmset("FUNDING_RATE_EXCHANGES", {
                "symbols": ujson.dumps(global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE), "time": time.time()
            })
            i_live_transit_station("main_instance", frequency=120)

        except:
            print(f"funding_rate_main {traceback.format_exc()}")
        await asyncio.sleep(fetch_timeout)


# 提供交易对的资金费率
async def get_funding_rate(symbol):
    if not global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE:
        res = await libs_price_async.redis_db_control.async_connection.hgetall("FUNDING_RATE_EXCHANGES")
        global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE = ujson.loads(res.get("symbols", '{}'))

    funding_rate = global_variable.G_FOLLOW_EXCHANGE_FUNDING_RATE.get(symbol, 0)
    return float(funding_rate)


if __name__ == "__main__":
    asyncio.run(funding_rate_fetch())
    # f = asyncio.run(get_funding_rate("BTC-USDT"))
    # print(f)
