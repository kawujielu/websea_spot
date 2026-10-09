import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import asyncio
import traceback
import time
import hmac
import json
import hashlib
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession


class GateioApi:
    exchange_name = "gate"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = "https://api.gateio.ws"
        self.prefix = "/api/v4"
        self.order_status = {'open': 'new', 'closed': 'filled', 'cancelled': 'cancelled'}

    async def gen_sign(self, method, url, t, query_string=None, payload_string=None):
        m = hashlib.sha512()
        m.update((payload_string or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string or "", hashed_payload, t)
        sign = hmac.new(self._secret_.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return sign

    async def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    async def request(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        cookies = args.get('cookies', {})
        args['timeout'] = 15
        timestamp = str(time.time())
        request_path = '' if method == 'POST' else (await self.parse_params_to_str(data))
        query_string = '' if method == 'POST' else request_path.replace('?', '')
        body = json.dumps(data) if method == 'POST' else ''
        host = args['url'].replace(self.url, '')
        args['header'] = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        result = {}

        if signed:
            args['header']['KEY'] = self._apiKey_
            args['header']['Timestamp'] = timestamp
            args['header']['SIGN'] = await self.gen_sign(method, host, timestamp, query_string, body)
        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    params=query_string,
                                                    data=body,
                                                    headers=args['header'],
                                                    # proxy='http://127.0.0.1:7890',
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()

            result['code'] = r.status
        return result

    async def wallet(self, currency=None):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency

        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['available']) + float(i['locked']) for i in res}
        else:
            return result

    async def wallet_free(self, ):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['available']) for i in res if float(i['available'])}
        else:
            return result

    async def wallet_saved_address(self, currency):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/saved_address'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        args['data']['currency'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def create_order(self, symbol, side, amount, price, type='limit', account='spot'):
        """
        :param symbol:
        :param side:
        :param amount:
        :param price:
        :param type:
        :param account:
        :return:
        挂单中的委托状态是 open ，在数量全部成交之前保持为 open 。
        如果被全部吃掉，则订单结束，状态变成 closed 。
        假如全部成交之前，订单被撤销，不管是否有部分成交，状态都会变为 cancelled
        gateio 对于价格精度和数量精度 没有限制
        """
        if self.exchange_name in global_variable.PRECISION.keys():
            precision = global_variable.PRECISION[self.exchange_name].get(symbol, {})
        else:
            global_variable.PRECISION[self.exchange_name] = {}
            precision = {}
        if not precision:
            precision = await self.precision(symbol)
            global_variable.PRECISION[self.exchange_name][symbol] = precision

        if precision['amount_precision'] == 0:
            amount = int(amount)
        else:
            amount = round(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])
        if precision['minQty'] > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}
        # 買賣方向. Buy：買入, Sell：賣出
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['account'] = account
        args['data']['side'] = side.lower()
        args['data']['type'] = type
        args['data']['amount'] = str(amount)
        args['data']['price'] = str(price)
        result = await self.request(args)
        if result['code'] == 200 or result['code'] == 201:
            data = json.loads(result['content'])
            data['orderId'] = data['id']
            data['status'] = self.order_status.get(data['status'], data['status']).upper()
            return data
        else:
            return result

    async def get_orders(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders/{orderId}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        # args['data']['limit'] = 10
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = self.order_status.get(res['status'], res['status']).upper()
            res['fillsz'] = float(res['filled_total']) / float(res['fill_price']) if float(res['fill_price']) else 0

            return res
        else:
            return result

    async def get_open_orders(self, symbol, status):
        # 查询订单列表
        """
        :param symbol:
        :param status: status: 基于状态查询订单列表,open - 挂单中 finished - 已结束
        :return:
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['status'] = status

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_order(self, symbol, orderId):
        # 撤销单个订单
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders/{orderId}'
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5, interval=0):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/order_book'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['limit'] = limit
        args['data']['interval'] = interval

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def precision(self, symbol=None):
        args = dict()
        args['url'] = f"{self.url}{self.prefix}/spot/currency_pairs/{symbol.replace('-', '_')}"
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            content = json.loads(result['content'])
            precision = {'price_precision': content['precision'], 'amount_precision': content['amount_precision'],
                         'minQty': float(content['min_base_amount'])}
            return precision
        else:
            return result

    async def get_Trades(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/my_trades'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['order_id'] = orderId
        # args['data']['limit'] = 10
        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            # return json.loads(result['content'])
            res = []
            for i in json.loads(result['content']):
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['create_time'])))
                d = {
                    'side': i['side'].upper(),
                    'amount': float(i['amount']),
                    'tradeId': i['id'],
                    'price': float(i['price']),
                    'fee': i['fee'],
                    'feecoin': i['fee_currency'],
                    'time': ts,
                    'orderId': i['order_id'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res
        else:
            return result

    async def get_symbols(self):
        # 行情信息
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/currencies'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def get_tickers(self):
        # 行情信息
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/tickers'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def currency(self):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/currencies'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def withdraw(self):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/withdraw_status'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_transfer(self, currency, amount, transfer_type, currency_pair):
        # 全仓杠杆账户划转 执行现货账户与全仓杠杆账户之间的划转
        # 1: 主账户向全仓杠杆账户划转 2: 全仓杠杆账户向主账户划转
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/transfers'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['amount'] = amount
        if transfer_type == 1:
            args['data']['from'] = 'spot'
            args['data']['to'] = 'margin'
        else:
            args['data']['from'] = 'margin'
            args['data']['to'] = 'spot'
        args['data']['currency_pair'] = currency_pair
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_loan(self, currency, amount):
        # 杠杆账户借贷 申请借贷
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/loans'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['amount'] = amount
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_repay(self, currency, amount):
        # 杠杆账户归还借贷 获取杠杆账户归还借贷
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/repayments'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['asset'] = currency
        args['data']['amount'] = amount
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_account(self, currency_pair=None):
        # 获取所有杠杆资产信息
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if currency_pair:
            args['data']['currency_pair'] = currency_pair
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_loan_list(self, currency=None, limit=None, offset=0, reverse=False):
        # 查询借贷记录
        """
        必须发送txId 或 startTime，txId 优先。
        响应返回为降序排列。
        如果发送isolatedSymbol，返回指定逐仓symbol指定asset的借贷记录。
        查询时间范围最大不得超过30天。
        若startTime和endTime没传，则默认返回最近7天数据
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/loans'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if limit:
            args['data']['limit'] = limit
        if offset:
            args['data']['offset'] = offset
        if reverse:
            args['data']['reverse'] = reverse
        args['data']['status'] = 0
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_repay_list(self, currency=None, loan_id=None, limit=None, offset=0, reverse=False):
        # 查询还贷记录
        """
        必须发送txId 或 startTime，txId 优先。
        响应返回为降序排列。
        如果发送isolatedSymbol，返回指定逐仓symbol指定asset的借贷记录。
        查询时间范围最大不得超过30天。
        若startTime和endTime没传，则默认返回最近7天数据
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/repayments'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if loan_id:
            args['data']['loan_id'] = loan_id
        if limit:
            args['data']['limit'] = limit
        if offset:
            args['data']['offset'] = offset
        if reverse:
            args['data']['reverse'] = reverse
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_transfer_list(self, currency=None, book_type=None, from_account=None, to_account=None, page=1,
                                   limit=10):
        # 查询杠杆账户变动历史
        '''
        响应返回为降序排列。
        查询时间范围最大不得超过30天。
        '''
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/account_book'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if book_type:
            args['data']['type'] = book_type
        if from_account:
            args['data']['from'] = from_account
        if to_account:
            args['data']['to'] = to_account
        args['data']['page'] = page
        args['data']['limit'] = limit
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cross_margin_data(self):
        # 获取全仓杠杆利率及限额
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def max_borrowable(self, currency=None):
        # 获取全仓杠杆利率及限额
        args = dict()
        args['url'] = '{}/sapi/v1/margin/maxBorrowable'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['asset'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def max_transferble(self, currency=None):
        # 获取全仓杠杆利率及限额
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/transferable'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_hourly_rate(self, currencies=None):
        # 获取全仓杠杆利率及限额
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/estimate_rate'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currencies:
            args['data']['currencies'] = currencies
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_currencies(self):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/currencies'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_currency(self, currency):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/currencies/{currency}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_accounts(self, currency=None):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_account_mode(self):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/account_mode'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_borrowable(self, currency):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/borrowable'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_transferable(self, currency):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/transferable'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_loans(self, currency, amount, unified_type='borrow', repaid_all=False, text=None):
        # 借入或还款
        '''
        unified_type:  borrow - 借入 , repay - 还款
        '''
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/loans'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['amount'] = amount
        args['data']['type'] = unified_type
        if repaid_all:
            args['data']['repaid_all'] = repaid_all
        if text:
            args['data']['text'] = text
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def find_unified_loan(self, currency=None, limit=100, page=1):
        # 查询借贷记录
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/loan_records'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if limit:
            args['data']['limit'] = limit
        if page:
            args['data']['page'] = page
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_loan_records(self, currency=None, unified_type=None, limit=100, page=1):
        # 查询借贷记录
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/loan_records'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if unified_type:
            args['data']['type'] = unified_type
        if limit:
            args['data']['limit'] = limit
        if page:
            args['data']['page'] = page
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def unified_interest_records(self, currency=None, limit=100, page=1):
        # 查询借贷记录
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/unified/interest_records'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if limit:
            args['data']['limit'] = limit
        if page:
            args['data']['page'] = page
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def get_contract_symbols(self):
        # 行情信息
        args = dict()
        settle = 'usdt'
        args['url'] = f'{self.url}{self.prefix}/futures/{settle}/contracts'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


gateio_instance = GateioApi()
global_variable.EXTERNAL_EXCHANGE_INSTANCES[gateio_instance.exchange_name] = gateio_instance


async def main():
    exchanges = [GateioApi(api_key='4cb40d8969cafb0f4d360ea6030d768b',
                           secret='ded3a8f1e5cf658a6e9cc1eda6b8de8e3fde8ff69b10a89493fd4c7db62bb019')]
    try:
        tasks = [asyncio.create_task(ex.wallet_free()) for ex in exchanges]
        for mm in tasks:
            print(await mm)
        # mm = await asyncio.wait(tasks)
        # print(mm)
    except:
        print(f"{traceback.format_exc()}")


if __name__ == "__main__":
    api = {'apiKey': 'f483ee25a4b44935a6324437e4bcc3f9',
           'secret': '0f93fb419b3350af79923cda0d9517bffd9a63890fb88418340afdc5e6d45cbb'}
    bb = GateioApi(api_key=api['apiKey'], secret=api['secret'])
    # wallet = asyncio.run(bb.wallet())
    amount = 0.00000001
    price = 22363.9
    symbol = 'BTC-USDT'
    side = 'SELL'
    print(amount * price)
    wallet = asyncio.run(bb.create_order(symbol='BTC-USDT', side=side, amount=amount, price=price))
    orderId = '289334853198'
    # orderId = '289324676615'
    # orderId = '289332846754'
    # wallet = asyncio.run(bb.cancel_order(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_orders(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_Trades(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.wallet())
    # wallet = asyncio.run(bb.wallet_free())
    # {'BTC': 0.0001, 'USDT': 6.76361}
    from pprint import pprint

    pprint(wallet)

# {'content': '{"label":"INVALID_PARAM_VALUE","message":"Invalid amount, 1e-05"}', 'code': 400}
