# coding=utf-8
import json, time
import pandas as pd
import sys, os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from scaffold.aiohttp import G_RequestSession

# 不提示警告
pd.set_option('mode.chained_assignment', None)
CURRENCY = {'AQ': 24, 'USDT': 2}


class A_INTERFACES:
    exchange_name = "abc"

    def __init__(self):
        self.host = 'https://bapi.abitex.me/api/'
        self.token = 'http://8.210.84.85:17468/api/token',
        self.host1 = 'https://riskapi.websea.work/api/'
        self.token1 = 'c1cf4185b2bed317aeb6e6674491fbef'
        self.host2 = 'https://riskapi.websea.work/api/'
        self.token2 = 'c1cf4185b2bed317aeb6e6674491fbef'
        self.A_API_TOKEN = "372c2099311c7b99d6213d7f51279ea1"
        self.deposit_status = {1: '待审核', 2: '已确认', 3: '成功', 4: '确认中', 5: '已反驳', 6: '排队中', 7: '已失败'}
        self.withdraw_status = {0: '审核中', 1: '已通过', 2: '已撤销', 3: '排队中', 5: '打包中', 7: '确认中', 9: '已确认', 11: '失败',
                                12: '已反驳'}
        self.user_id = 99571
        self.backstage_token = "c1cf4185b2bed317aeb6e6674491fbef"

    async def request(self, args):
        method = args['method']
        if not 'timeout' in args:
            args['timeout'] = 10

        if not 'data' in args:
            args['data'] = {}

        params = {} if method == 'POST' else args['data']
        data = args['data'] if method == 'POST' else {}

        result = {}
        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    params=params,
                                                    data=data,
                                                    # headers=headers,
                                                    # proxy='http://127.0.0.1:7890',
                                                    timeout=5,
                                                    # verify=False
                                                    ) as r:
            result['content'] = await r.text()
            result['code'] = r.status
        return result

    # 币种列表
    async def currency_list(self, symbol=None):
        args = dict()
        # args['url'] = f'{self.host1}currency/list?token={self.token1}'
        args['url'] = 'https://riskapi.websea.work/api/currency/list?token=c1cf4185b2bed317aeb6e6674491fbef'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['name'] = symbol

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    # 提币列表
    async def get_withdrawals(self, symbol):
        # type_withdrawals = {'1': '待审核', 2: '已确认', 3: '打包中', 4: '确认中', 6: '排队中', 5: '已驳回', 7: '已失败', 8: '异常'}
        args = dict()
        args['url'] = f'{self.host1}transfer/takeoutdata?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['currency'] = self.currency_list(symbol)['result'][0]['id']
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    # 充币地址
    async def get_deposits(self, symbol):
        # type_deposits = {0: '待审核', 9: '已确认',12:'已驳回'}
        args = dict()
        args['url'] = f'{self.host1}transfer//rechargedata?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['currency'] = await self.currency_list(symbol)['result'][0]['id']
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    # 充币数据
    async def get_deposit_list(self, page=None, page_size=None, user_id=None, currency_id=None, amount=None,
                               address=None, tx_hash=None, from_adress=None, min_time=None, max_time=None,
                               status=None):
        """
        :param page:第几页
        :param page_size:分页大小
        :param user_id:用户id
        :param currency_id:充币币种
        :param amount:充值数量
        :param address:充值地址
        :param tx_hash:交易hash
        :param from_adress:来源地址
        :param min_time:开始时间
        :param max_time:结束时间
        :param status:状态 0提交中 1待确认 3排队中 5排队中 9已确认 11失败 12已驳回
        :return:
        """
        args = dict()
        args['url'] = f'{self.host1}transfer/cashinlist?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()
        if page:
            args['data']['page'] = page
        if page_size:
            args['data']['page_size'] = page_size
        if user_id:
            args['data']['user_id'] = user_id
        if currency_id:
            args['data']['currency_id'] = currency_id
        if amount:
            args['data']['amount'] = amount
        if address:
            args['data']['address'] = address
        if tx_hash:
            args['data']['tx_hash'] = tx_hash
        if from_adress:
            args['data']['from_adress'] = from_adress
        if min_time:
            args['data']['min_time'] = min_time
        if max_time:
            args['data']['max_time'] = max_time
        if status:
            args['data']['status'] = status
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    # 提币数据
    async def get_withdraw_list(self, page=None, page_size=None, user_id=None, currency_id=None, min_amount=None,
                                max_amount=None, address=None, tx_hash=None, from_adress=None, min_time=None,
                                max_time=None, status=None):
        """
        :param page:第几页
        :param page_size:分页大小
        :param user_id:用户id
        :param currency_id:充币币种
        :param amount:充值数量
        :param address:充值地址
        :param tx_hash:交易hash
        :param from_adress:来源地址
        :param min_time:开始时间
        :param max_time:结束时间
        :param status:状态 0提交中 1待确认 3排队中 5排队中 9已确认 11失败 12已驳回
        :return:
        """
        args = dict()
        args['url'] = f'{self.host1}transfer/takeoutlist?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()
        if page:
            args['data']['page'] = page
        if page_size:
            args['data']['page_size'] = page_size
        if user_id:
            args['data']['user_id'] = user_id
        if currency_id:
            args['data']['currency'] = currency_id
        if min_amount:
            args['data']['min_amount'] = min_amount
        if max_amount:
            args['data']['max_amount'] = max_amount
        if address:
            args['data']['address'] = address
        if tx_hash:
            args['data']['tx_hash'] = tx_hash
        if from_adress:
            args['data']['from_adress'] = from_adress
        if min_time:
            args['data']['min_time'] = min_time
        if max_time:
            args['data']['max_time'] = max_time
        if status:
            args['data']['status'] = status
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def fund_list(self, ID=None, currency=None, page=None, page_size=None):
        args = dict()
        args['url'] = f'{self.host}funds/list?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['user_id'] = ID
        args['data']['currency'] = currency
        args['data']['page'] = page
        args['data']['page_size'] = page_size
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def get_transfer_spotTOspot(self, symbol, from_user_id, to_user_id, amount, remark='tset'):
        """
        币币划转提交参数示例:
        from_status:  1  币币钱包状态1
        to_status:  1  币币钱包状态1
        from_user_id:  23219 转出用户
        to_user_id:  23254  转入用户
        currency_id:  2 币种ID
        amount:  100.1  数量
        remark:  测试  备注
        """
        args = dict()
        args['url'] = f'{self.host}transfer/index?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['from_status'] = 1
        args['data']['to_status'] = 1
        args['data']['from_user_id'] = from_user_id
        args['data']['to_user_id'] = to_user_id
        currency_id = self.currency_list(symbol)['result'][0]['id']
        args['data']['currency_id'] = currency_id
        args['data']['amount'] = amount
        args['data']['remark'] = remark
        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            print(f'币币转币币 转出id:{from_user_id} 转入id:{to_user_id} {symbol} id号:{currency_id} 划转数量:{amount} 结果:{result}')
            return result
        else:
            return result

    async def get_transfer_spotTOcontract(self, to_symbol, from_user_id, to_user_id, amount, remark='test'):
        """
        币币转合约:
        from_status:  1 币币钱包状态1
        to_status:  5 合约钱包状态5
        to_symbol:  BTC-USDT 转入合约交易对
        from_user_id: 23219 转出用户
        to_user_id:  23254|转入用户
        currency_id:  2 币种ID 注意 币种ID 应该和交易对的结算币一致 如转入交易对为 BTC-AQ 则币种ID为 24
        amount:  100 数量
        remark:  测试 备注
        """
        args = dict()
        args['url'] = f'{self.host}transfer/index?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['from_status'] = 1
        args['data']['to_status'] = 5
        args['data']['to_symbol'] = to_symbol
        args['data']['from_user_id'] = from_user_id
        args['data']['to_user_id'] = to_user_id
        args['data']['currency_id'] = CURRENCY[to_symbol.split('-')[1]]
        args['data']['amount'] = amount
        args['data']['remark'] = remark

        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            print(f'币币转合约 转出id:{from_user_id} 转入id:{to_user_id} 转入交易对:{to_symbol} 划转数量:{amount} 结果:{result}')
            return result
        else:
            return result

    async def get_transfer_contractTOcontract(self, from_symbol, to_symbol, from_user_id, to_user_id, amount,
                                              remark='test'):
        """
        合约转合约:
        from_status :5 合约钱包状态5
        to_status :5 合约钱包状态5
        from_symbol :BTC-USDT 转入合约交易对
        to_symbol :ETH-USDT 转入合约交易对
        from_user_id :23219 转出用户
        to_user_id :23254 转入用户
        currency_id :2 币种ID 注意 币种ID 应该和交易对的结算币一致 如转入交易对为 BTC-AQ 则币种ID为 24
        amount :100 数量
        remark :测试 备注
        """
        args = dict()
        args['url'] = f'{self.host}transfer/index?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['from_status'] = 5
        args['data']['to_status'] = 5
        args['data']['from_symbol'] = from_symbol
        args['data']['to_symbol'] = to_symbol
        args['data']['from_user_id'] = from_user_id
        args['data']['to_user_id'] = to_user_id
        args['data']['currency_id'] = CURRENCY[to_symbol.split('-')[1]]
        args['data']['amount'] = amount
        args['data']['remark'] = remark
        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            print(
                f'合约转合约 转出id:{from_user_id} 转入id:{to_user_id} 转出交易对:{from_symbol} 转入交易对:{to_symbol} 划转数量:{amount} 结果:{result}')
            return result
        else:
            return result

    async def get_transfer_contractTOspot(self, from_symbol, from_user_id, to_user_id, amount, remark='test'):
        """
       合约转币币:
        from_status :5 合约钱包状态5
        to_status :1 币币钱包状态1
        from_symbol :BTC-USDT 转入合约交易对
        from_user_id :23219 转出用户
        to_user_id :23254 转入用户
        currency_id :2 币种ID 注意 币种ID 应该和交易对的结算币一致 如转入交易对为 BTC-AQ 则币种ID为 24
        amount :100|数量
        remark  :测试|备注
        """
        args = dict()
        args['url'] = f'{self.host}transfer/index?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['from_status'] = 5  # 合约
        args['data']['to_status'] = 1  # 现货
        args['data']['from_symbol'] = from_symbol
        args['data']['from_user_id'] = from_user_id
        args['data']['to_user_id'] = to_user_id
        args['data']['currency_id'] = CURRENCY[from_symbol.split('-')[1]]
        args['data']['amount'] = amount
        args['data']['remark'] = remark

        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            print(f'合约转币币 转出id:{from_user_id} 转入id:{to_user_id} 转出交易对:{from_symbol} 划转数量:{amount} 结果:{result}')
            return result
        else:
            return result

    async def get_deposit_address(self, symbol):
        """
        获取用户充币地址
        """
        args = dict()
        args['url'] = f'{self.host2}dq/useraddress?currency_name={symbol}&token={self.token2}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            return result
        else:
            return result

    async def dq_add(self, from_user_id, to_user_id, amount, symbol, notes):
        args = dict()
        args['url'] = f'{self.host2}dq/add?token={self.token2}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['from_user_id'] = from_user_id
        args['data']['to_user_id'] = to_user_id
        args['data']['amount'] = amount
        currency_id = self.currency_list(symbol)['result'][0]['id']
        args['data']['currency_id'] = currency_id
        args['data']['notes'] = notes
        result = await self.request(args)
        if result['code'] == 200:
            result = json.loads(result['content'].decode('utf-8'))
            return result
        else:
            return result

    # 充币数据
    async def deposit_history(self):
        args = dict()
        args['url'] = f'{self.host1}transfer/cashinlist?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()

        args['data']['user_id'] = self.user_id
        result = await self.request(args)
        mm = []
        if result['code'] == 200:
            res = json.loads(result['content'].decode('utf-8'))
            for i in res:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['currency_txt']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('tx_hash', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'deposit'
                tmp['status'] = i['status']
                tmp['status1'] = self.deposit_status.get(i['status'], i['status'])
                mm.append(tmp)
            return mm
        else:
            return result

    # 提币数据
    async def withdraw_history(self, ):

        args = dict()
        args['url'] = f'{self.host1}transfer/takeoutlist?token={self.token1}'
        args['method'] = 'GET'
        args['data'] = dict()

        args['data']['user_id'] = self.user_id
        result = await self.request(args)
        mm = []
        if result['code'] == 200:
            res = json.loads(result['content'].decode('utf-8'))
            for i in res:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['currency_txt']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('tx_hash', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'withdraw'
                tmp['status'] = i['status']
                tmp['status1'] = self.withdraw_status.get(i['status'], i['status'])
                mm.append(tmp)
            return mm
        else:
            return result

    async def transferassets(self, ):

        args = dict()
        args[
            'url'] = f'{self.host}/transferassets2?language=1&timesamp={int(time.time())}&token={self.host}&pageSize=20&page=1'

        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))

        else:
            return result

    async def contract_treaty_holdlist(self, page=None, page_size=None, user_id=None, is_full=None, symbol=None):
        # 当前持仓列表接口
        args = dict()
        args['url'] = f'https://riskapi.websea.work/api/treaty/holdlist?token={self.backstage_token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol_name'] = symbol
        if page:
            args['data']['page'] = page
        if page_size:
            args['data']['page_size'] = page_size
        if user_id:
            args['data']['user_id'] = user_id
        if is_full:
            args['data']['is_full'] = is_full

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_treaty_fullholdlist(self, page=None, page_size=None, user_id=None, is_full=None, symbol=None):
        # 全仓 当前持仓列表接口
        args = dict()
        args['url'] = f'https://riskapi.websea.work/api/treaty/fullholdlist?token={self.backstage_token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol_name'] = symbol
        if page:
            args['data']['page'] = page
        if page_size:
            args['data']['page_size'] = page_size
        if user_id:
            args['data']['user_id'] = user_id
        if is_full:
            args['data']['is_full'] = is_full

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def userid_futurefee(self, ):
        # 手续费为0的用户
        args = dict()
        args['url'] = f'https://riskapi.websea.work/api/user/futurefee?token={self.backstage_token}'
        args['method'] = 'GET'
        args['data'] = dict()
        
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    # res = A_INTERFACES().dq_add(from_user_id=1, to_user_id=99571, amount=0.048, symbol='DASH', notes='划转接口测试')
    # print(res)
    # pass
    # symbol = 'AVN'
    currency = asyncio.run(A_INTERFACES().currency_list())
    print(currency)
    # res = A_INTERFACES().get_deposit_address(symbol='USDT')
    # print(res)
