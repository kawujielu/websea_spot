import asyncio
import math
import json
import sys, os
from datetime import datetime

file = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(file)
from config.infor_load import contract_host
from config.infor import SYMBOLS_PAIR
from config.infor_contract import SYMBOLS_CONTRACT_OUT, SYMBOLS_CONTRACT_PAIR
from libs.requestSession import G_RequestSession
from libs import heartbeat, sendmessage
from contract.contract_setting import capitalrateparam

ERROR = []
PRECISION_EXCHANGE = {}
PRECISION_EXCHANGE_PRICE = {}
ADJUSTED_FUNDING_RATE_CAP_FLOOR = {}

path = sys.path[0]
filename = f'{path}/contract_exchange_symbols.json'

headers = {
    'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}


class BinanceApi():
    def __init__(self):
        self.ex = 'bn'

    async def get_precision(self):
        precision_list = {}
        url = f'https://fapi.binance.com/fapi/v1/exchangeInfo'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['symbols']:
                    # PENDING_TRADING 待上市
                    # TRADING 交易中
                    # PRE_DELIVERING 预交割
                    # DELIVERING 交割中
                    # DELIVERED 已交割
                    # PRE_SETTLE 预结算
                    # SETTLING 结算中
                    # CLOSE 已下架
                    if i['status'] in ['TRADING', 'PENDING_TRADING']:
                        precision = {}
                        for j in i['filters']:
                            if j['filterType'] == 'PRICE_FILTER':
                                precision['minPrice'] = float(j['minPrice'])
                                precision['price_precision'] = -math.ceil(math.log10(float(float(j['tickSize']))))

                            if j['filterType'] == 'LOT_SIZE':
                                precision['minQty'] = float(j['minQty'])
                                precision['amount_precision'] = -math.ceil(math.log10(float(float(j['stepSize']))))
                        precision_list[i['baseAsset'] + '-' + i['quoteAsset']] = precision
        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def interval_hours(self, symbols):
        funding_interval_hours = {}
        url = "https://fapi.binance.com/fapi/v1/fundingInfo"
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:

                res = await r.text()
                res = json.loads(res)
                for r in res:
                    s = r["symbol"].replace("USDT", "-USDT")
                    if s in symbols:
                        f = r["fundingIntervalHours"]
                        funding_interval_hours[s] = {'fundingIntervalHours': int(f),
                                                     'maxFundingRate': float(r["adjustedFundingRateCap"]),
                                                     'minFundingRate': float(r["adjustedFundingRateFloor"])}


        except:
            ERROR.append(self.ex)
        ADJUSTED_FUNDING_RATE_CAP_FLOOR[self.ex] = funding_interval_hours


class OkexApi:
    def __init__(self, ):
        self.ex = 'okex'

    async def get_precision(self):
        precision_list = {}
        instType = 'SWAP'
        url = f'https://www.okx.com/api/v5/public/instruments?instType={instType}'
        # 产品状态 state
        # live：交易中
        # suspend：暂停中
        # preopen：预上线，如：交割和期权的新合约在 live 之前，会有 preopen 状态
        # test：测试中（测试产品，不可交易）
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if res['code'] == '0':
                    for i in res['data']:
                        if i['state'] in ['live']:
                            precision = {}
                            precision['price_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
                            precision['minQty'] = float(i['minSz'])
                            precision['amount_precision'] = -math.ceil(math.log10(float(float(i['lotSz']))))
                            # precision['amount_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
                            precision_list[i['instFamily']] = precision

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        url = 'https://www.okx.com/api/v5/market/tickers?instType=SWAP'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if res['code'] == '0':
                    for i in res['data']:
                        precision_list[i['instId']] = i['last']
        except:
            ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list

    async def interval_hours_symbol(self, symbol, funding_interval_hours):
        url = f"https://www.okx.com/api/v5/public/funding-rate?instId={symbol}-SWAP"
        try:
            async with G_RequestSession.request.get(url, headers=headers) as r:
                res = await r.json()
                if res['code'] == '0':
                    f = (float(res['data'][0]["nextFundingTime"]) - float(res['data'][0]["fundingTime"])) / 1000 / 60 / 60
                    funding_interval_hours[symbol] = {'fundingIntervalHours': int(f)}
        except:
            print('error', self.ex, symbol)

    async def interval_hours(self, symbols):
        funding_interval_hours = {}
        # tasks = [asyncio.create_task(self.fund_rate(symbol, usdt_busd_zone_list)) for symbol in contract_symbols]
        # await asyncio.wait(tasks)
        for symbol in symbols:
            await self.interval_hours_symbol(symbol, funding_interval_hours)
            await asyncio.sleep(0.2)

        ADJUSTED_FUNDING_RATE_CAP_FLOOR[self.ex] = funding_interval_hours


class GateioApi:
    def __init__(self, ):
        self.ex = 'gate'

    # in_delisting 合约下线中
    # order_price_round	string	false	none	委托价格最小单位
    # order_size_min	integer(int64)	false	none	最小下单数量
    # "name": "KNC_USDT",
    async def get_precision(self):
        precision_list = {}
        url = 'https://api.gateio.ws/api/v4/futures/usdt/contracts'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res:
                    if not i['in_delisting']:
                        precision = {}
                        symbol = i['name'].replace('_', '-')
                        precision['price_precision'] = -math.ceil(math.log10(float(float(i['order_price_round']))))
                        precision['amount_precision'] = float(i['order_size_min'])

                        precision_list[symbol] = precision

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def interval_hours(self, symbols):
        funding_interval_hours = {}
        url = 'https://api.gateio.ws/api/v4/futures/usdt/contracts'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for r in res:
                    s = r["name"].replace("_", "-")
                    if s in symbols:
                        f = r["funding_interval"] / 3600
                        funding_interval_hours[s] = {'fundingIntervalHours': int(f)}

        except:
            ERROR.append(self.ex)
        ADJUSTED_FUNDING_RATE_CAP_FLOOR[self.ex] = funding_interval_hours


class AbcApi:

    def __init__(self, ):
        self.ex = 'abc'

    async def get_precision(self):
        precision_list = {}
        url = contract_host + '/qapi-v1/symbol/precision'

        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()

                for symbol, v in res['result'].items():
                    if symbol not in SYMBOLS_CONTRACT_OUT:
                        precision_list[symbol] = {'price_precision': int(v['price']), 'amount_precision': int(v['amount']), 'minQty': int(v['minQuantity'])}

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def interval_hours(self, symbols):
        funding_interval_hours = {}
        try:
            res = await capitalrateparam()

            for r in res:
                s = r["name"]
                if s in symbols:
                    f = r["cycle"]
                    funding_interval_hours[s] = {'fundingIntervalHours': int(f),
                                                 'maxFundingRate': float(r["sectionB"]),
                                                 'minFundingRate': float(r["sectionA"])}


        except:
            ERROR.append(self.ex)
        ADJUSTED_FUNDING_RATE_CAP_FLOOR[self.ex] = funding_interval_hours


async def contract_exchange_symbols():
    exchanges = {'bn': BinanceApi(),
                 'okex': OkexApi(),
                 'gate': GateioApi(),
                 'abc': AbcApi(),

                 }
    try:
        EXCHANGE_SYMBOLS_LAST = json.load(open(filename))
    except:
        EXCHANGE_SYMBOLS_LAST = {i: {} for i in exchanges}
        EXCHANGE_SYMBOLS_LAST['time'] = ""
        # json.dump(exchange_symbols_last, open(filename, 'w'))

    for ex, Api in exchanges.items():
        await Api.get_precision()
    if ERROR:
        mess = f'error：-->exchange contract_online_offline symbol: {ERROR}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')
        return

    PRECISION_EXCHANGE['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    json.dump(PRECISION_EXCHANGE, open(filename, 'w'))
    last_time = EXCHANGE_SYMBOLS_LAST['time']
    now_time = PRECISION_EXCHANGE['time']
    msg = ""

    for ex, ex_symbols in PRECISION_EXCHANGE.items():
        if ex not in ['time', ]:
            if EXCHANGE_SYMBOLS_LAST.get(ex):
                online = set(ex_symbols) - set(EXCHANGE_SYMBOLS_LAST[ex])
                offline = set(EXCHANGE_SYMBOLS_LAST[ex]) - set(ex_symbols)
                if ex not in ['abc']:
                    # online = [f"{s}❗" if s in SYMBOLS_CONTRACT_PAIR else s for s in online]
                    # offline = [f"{s}❗" if s in SYMBOLS_CONTRACT_PAIR else s for s in offline]

                    online = [f"{s}[现|合]" if s in set(SYMBOLS_CONTRACT_PAIR) & set(SYMBOLS_PAIR) else f"{s}[合]" if s in SYMBOLS_CONTRACT_PAIR else f"{s}[现]" for s in online if s in SYMBOLS_CONTRACT_PAIR + SYMBOLS_PAIR]
                    offline = [f"{s}[现|合]" if s in set(SYMBOLS_CONTRACT_PAIR) & set(SYMBOLS_PAIR) else f"{s}[合]" if s in SYMBOLS_CONTRACT_PAIR else f"{s}[现]" for s in offline if s in SYMBOLS_CONTRACT_PAIR + SYMBOLS_PAIR]

                if online or offline:
                    msg += f"交易所：{ex}\n"
                    msg += f"      ● 上线：{'、'.join(online)}\n" if online else ""
                    msg += f"      ● 下线：{'、'.join(offline)}\n" if offline else ""
            else:
                msg += f'合约添加【{ex}】交易所上下线新币监控\n'
    if msg:
        message = f"{now_time} - {last_time}\n" \
                  f"【合约-交易对】上下线检测\n" \
                  f"其中 a-b[现] :a-b在abc现货区上线、a-b[合] :a-b在abc合约区上线。此时可以判断一下做市、对冲是否切换交易所\n{msg}"
        print(message)
        sendmessage.send_telegram_msg(message=message,
                                      ser='updata_currency')
    await heartbeat.i_live_well(server='【合约】交易所交易对上下线监控', frequency=60 * 61 * 2, index=29)


async def contract_run():
    try:
        await contract_exchange_symbols()
    except Exception as e:
        mess = f'error：-->exchange contract_online_offline symbol {e}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(contract_run())
