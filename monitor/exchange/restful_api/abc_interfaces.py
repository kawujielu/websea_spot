# coding=utf-8
import asyncio

import requests, json, datetime, time
import pandas as pd
import urllib3
from loguru import logger
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from config.infor_load import backstage_host, token
from libs.requestSession import G_RequestSession

# 不提示警告
pd.set_option('mode.chained_assignment', None)
CURRENCY = {'USDT': 2}


class AINTERFACES:
    exchange_name = "abc"

    def __init__(self):
        self.host = backstage_host + 'api/'
        self.token = token
        self.deposit_status = {'0': '提交中', '1': '待确认', '3': '排队中', '5': '排队中', '9': '已确认', '11': '已失败', '12': '已反驳'}
        self.withdraw_status = {'0': '审核中', '1': '已通过', '2': '已撤销', '3': '排队中', '5': '打包中', '7': '确认中', '9': '已确认', '11': '失败',
                                '12': '已反驳'}

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
                                                    timeout=15,
                                                    # ssl=False
                                                    ) as r:
            result['content'] = await r.text()
            result['code'] = r.status
        if result['code'] != 200:
            logger.error(f"{result}, {args}")
        return result

    # 币种列表
    async def currency_list(self, currency=None):
        args = dict()
        args['url'] = f'{self.host}currency/list?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if currency:
            args['data']['name'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    # 提币列表
    async def get_withdrawals(self, currency):
        # type_withdrawals = {'1': '待审核', 2: '已确认', 3: '打包中', 4: '确认中', 6: '排队中', 5: '已驳回', 7: '已失败', 8: '异常'}
        args = dict()
        args['url'] = f'{self.host}transfer/takeoutdata?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['currency'] = (await self.currency_list(currency))['result'][0]['id']
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    # 充币数据
    async def get_deposit_list(self, page, page_size, user_id=None, currency_id=None, amount=None,
                               address=None, tx_hash=None, from_adress=None, start_time=None, end_time=None,
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
        args['url'] = f'{self.host}transfer/cashinlist?token={self.token}'
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
        if start_time:
            args['data']['min_time'] = start_time
        if end_time:
            args['data']['max_time'] = end_time
        if status:
            args['data']['status'] = status
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    # 提币数据
    async def get_withdraw_list(self, page=None, page_size=None, user_id=None, currency_id=None, min_amount=None,
                                max_amount=None, address=None, tx_hash=None, from_adress=None, status=None,
                                start_time=None, end_time=None):
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
        # :param status:状态 0提交中 1待确认 3排队中 5排队中 9已确认 11失败 12已驳回
        :param status:状态 0审核中 1已通过 2已撤销 3排队中 5打包中 7确认中 9已确认 11失败 12已驳回
        :return:
        """
        args = dict()
        args['url'] = f'{self.host}transfer/takeoutlist?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if page:
            args['data']['page'] = int(page)
        if page_size:
            args['data']['page_size'] = int(page_size)
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
        if start_time:
            args['data']['min_time'] = start_time
        if end_time:
            args['data']['max_time'] = end_time
        if status:
            args['data']['status'] = status
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def fund_list(self, user_id=None, wallet=None, currency=None, symbol=None, status=None):
        """
        资产列表
        :param user_id:账户
        :param wallet:钱包账户 1现金 2币币 3法币 4杠杠 5合约
        :param currency:币种查询多个使用英文逗号分隔，不传查全部（不传小概率查不全，对于风险计算之类的建议自行传参）
        :param symbol:交易对，逐仓账户类型钱包必须传，查询多个使用英文逗号分割，默认为空，传查全部（小概率查不全，对于风险计算之类的建议自行穿参）
        :param status:状态查询多个使用英文逗号分割，不传查全部（不传小概率查不全，对于风险计算之类的建议自行传参）
        :return:
        """
        args = dict()
        args['url'] = f'{self.host}funds/list?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if user_id:
            args['data']['user_id'] = user_id
        if wallet:
            args['data']['wallet'] = wallet
        if symbol:
            args['data']['symbol'] = symbol
        if currency:
            args['data']['currency'] = currency
        if status:
            args['data']['status'] = status

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    # 充币数据
    async def deposit_history(self, user_id):
        args = dict()
        args['url'] = f'{self.host}transfer/cashinlist?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()

        args['data']['user_id'] = user_id
        result = await self.request(args)
        mm = []
        if result['code'] == 200:
            res = json.loads(result['content'])
            for i in res['result']['data']:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['userId']
                tmp['currency'] = i['currency_name']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('tx_hash', '')
                tmp['amount'] = float(i.get('amount', 0))
                tmp['fee'] = float(i.get('fee', 0)) if i.get('fee', 0) else 0
                tmp['side'] = 'deposit'
                tmp['status'] = str(i['status'])
                tmp['ctime'] = i['create_time']
                tmp['mtime'] = i['mtime']
                tmp['time'] = datetime.datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status1'] = self.deposit_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm
        else:
            return result

    # 提币数据
    async def withdraw_history(self, user_id):
        args = dict()
        args['url'] = f'{self.host}transfer/takeoutlist?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()

        args['data']['user_id'] = user_id
        result = await self.request(args)
        mm = []
        if result['code'] == 200:
            res = json.loads(result['content'])
            for i in res['result']['data']:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['user_id']
                tmp['currency'] = i['currency_txt'].split('(')[0]
                tmp['address'] = i['address']
                tmp['hash'] = i.get('tx_hash', '')
                tmp['amount'] = float(i.get('amount', 0))
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'withdraw'
                tmp['ctime'] = i['ctime']
                tmp['mtime'] = i['mtime']
                tmp['time'] = datetime.datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.withdraw_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm
        else:
            return result

    async def transferassets(self, page=1, page_size=20, currency_id=None, from_user_id=None, to_user_id=None):

        args = dict()
        args['url'] = f'{self.host}transferassets?token={self.token}'

        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['page'] = page
        args['data']['page_size'] = page_size
        if currency_id:
            args['data']['currency_id'] = currency_id
        if from_user_id:
            args['data']['from_user_id'] = from_user_id
        if to_user_id:
            args['data']['to_user_id'] = to_user_id

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])

        else:
            return result

    async def contract_position(self, symbol=None, self_user=None, is_full=None):
        # 合约持仓数据
        """
        :param symbol : 交易对
        :param self_user : 是否去除量化用户 1，是，0否 ,2只返回量化用户
        :is_full : 是否全仓 1，是，0否
        :return:
        """
        args = dict()
        args['url'] = f'{self.host}contracthold/list?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        if self_user:
            args['data']['self_user'] = self_user
        if is_full:
            args['data']['is_full'] = is_full

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_treatybalance(self, user_id, wallet=5):
        # 合约等级用户持仓数据
        """
        :param symbol : 交易对
        :param level : 等级
        :return:
        """
        args = dict()
        args['url'] = f'{self.host}open/treatybalance?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['user_id'] = user_id
        args['data']['wallet'] = wallet

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_treaty_cost(self, page=None, page_size=None, min_time=None, max_time=None, user_id=None, is_full=None):
        # 合约等级用户持仓数据
        args = dict()
        args['url'] = f'{self.host}treaty/cost?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()
        if page:
            args['data']['page'] = page
        if page_size:
            args['data']['page_size'] = page_size
        if min_time:
            args['data']['min_time'] = min_time
        if max_time:
            args['data']['max_time'] = max_time
        if user_id:
            args['data']['user_id'] = user_id
        if is_full:
            args['data']['is_full'] = is_full

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_treaty_holdlist(self, page=None, page_size=None, user_id=None, is_full=None, symbol=None):
        # 当前持仓列表接口
        args = dict()
        args['url'] = f'{self.host}treaty/holdlist?token={self.token}'
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
        args['url'] = f'{self.host}treaty/fullholdlist?token={self.token}'
        # args['url'] = f'{self.host}cashuserhold/list?token={self.token}'
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

    async def userid_spotfee(self, ):
        # 手续费为0的用户
        args = dict()
        args['url'] = f'{self.host}user/spotfee?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def userid_futurefee(self, ):
        # 手续费为0的用户
        args = dict()
        args['url'] = f'{self.host}user/futurefee?token={self.token}'
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    from pprint import pprint

    end_time = int(time.time())
    start_time = int(end_time - 8 * 60 * 60)


    async def aa():
        sym = 'TRX-USDT'
        # res = await AINTERFACES().contract_position(symbol=sym,self_user=1,is_full=1)
        # print(res)
        # res = await AINTERFACES().contract_position(symbol=sym,self_user=1,is_full=0)
        # print(res)
        res = await AINTERFACES().contract_treaty_holdlist(page=1, page_size=100)
        pprint(res)

        # mm = await AINTERFACES().currency_list(currency=sym)
        # mm = await AINTERFACES().userid_spotfee()

        # for i in range(1, 5):
        #     print('----->>>>', i)
        #     res = await AINTERFACES().contract_treaty_cost(page=i, page_size=100, max_time=end_time, min_time=start_time, user_id=18)
        #
        #     for j in res['result']['data']:
        #         print(j)
        # for page in range(1,100):
        #     page_size = 50
        #     mm = await AINTERFACES().contract_treaty_fullholdlist(page=page, page_size=page_size,symbol=sym)
        #     for j in mm['result']['data']['Data']:
        #         print(page,j)
        #     if len(mm['result']['data']['Data']) < page_size:
        #         break
        # mm = await AINTERFACES().contract_treaty_holdlist(page=1, page_size=50, user_id=19,symbol='BTC-USDT')
        # print(mm)


    asyncio.run(aa())
