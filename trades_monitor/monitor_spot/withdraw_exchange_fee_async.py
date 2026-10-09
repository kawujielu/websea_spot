import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import time
import traceback
from libs.send_tglegram_msg import send_telegram_async
from exchanges.restful_api.abc_spot import AApi
from exchanges.restful_api.abc_interfaces import A_INTERFACES
from exchanges.restful_api.mexc import mexc_instance
from exchanges.restful_api.gateio import gateio_instance
from exchanges.restful_api.huobi import huobi_instance
from exchanges.restful_api.binance import bn_instance
from exchanges.restful_api.okex import okex_instance
from exchanges.restful_api.bitget import bitget_instance
from scaffold.mysql import G_MysqlSession, Hedge_MysqlSession
import asyncio
from libs import heartbeat
from libs import libs_price_async
from libs.chain_name_config import websea_chain_name, mxc_chain_name, gate_chain_name, huobi_chain_name, \
    okex_chain_name, bitget_chain_name, balance_chain_name
from libs.delisting_currency import off_spot_currency

'''
websea 提币手续费计算公式：
手续费收取类型有： 1.数量 ，2.CNY数量  3.比例  4.对标火币
具体的计算规则 已经整理好了：

提币手续费计算规则：
1. choose_take_fee_type 提笔手续费类型： 1. 数量 2.额度 3比例  4.对标火币

2.不同类型计算方式 ：
  2.1 数量=手续费*币种系列系数:     service_fee* take_out_rate
  2.2 额度=手续费额度换算成当前币种数量*币种系列系数:  take_fee_quota_one / (市场最新价（USDT） * 对人民的汇率)  *  take_out_rate
  2.3 比例=提币数量*比例:       提币数量 * takeout_fee_rate_one * take_out_rate
  2.4 火币=火币对应链的手续费： 调接口查火币手续费字段 
  2.4.1 火币手续费接口说明：
      拼接以下请求url：
      https://api.huobi.pro/v2/reference/currencies?currency=币种名称小写 比如usdt

      返回的chains列表数据 判断  base_chain_protocol = baseChainProtocol 或者 notes = displayName 
      取transactFeeWithdraw 火币手续费字段，不需要乘以币种系列系数


下面是火币手续费接口返回示例：
{
    "code":200,
    "data":[
        {
            "currency":"usdt",
            "assetType":1,
            "chains":[
                {
                    "chain":"usdterc20",
                    "displayName":"ERC20", //判断改字段和币种列表接口返回的notes字段是否相等
                    "fullName":"",
                    "baseChain":"ETH",
                    "baseChainProtocol":"ERC20", //判断改字段和币种列表接口返回的base_chain_protocol字段是否相等
                    "isDynamic":true,
                    "numOfConfirmations":64,
                    "numOfFastConfirmations":32,
                    "depositStatus":"allowed",
                    "minDepositAmt":"1",
                    "withdrawStatus":"allowed",
                    "minWithdrawAmt":"1",
                    "withdrawPrecision":6,
                    "maxWithdrawAmt":"1000000.000000000000000000",
                    "withdrawQuotaPerDay":"1000000.000000000000000000",
                    "withdrawQuotaPerYear":null,
                    "withdrawQuotaTotal":null,
                    "withdrawFeeType":"fixed",
                    "transactFeeWithdraw":"6.656017",
                    "addrWithTag":false,
                    "addrDepositTag":false
                }
            ],
            "instStatus":"normal"
        }
    ]
}
目前币种列表接口是  缺少提币类型是 2,3,需要的字段： 
choose_take_fee_type 提笔手续费类型 ，
take_fee_quota_one    提币手续费CNY额度
takeout_fee_rate_one    提币手续费比例

目前有227个链。   其中手续费收取方式分布情况  ：  
按照固定数量  105个
按照CNY数量   39个
按照比例    0个
对标火币   83个
'''

price_redis_db = libs_price_async.redis_db_market_price

CURRENCY_RATE = {}

hedge_exchange = {
    'bn': 'binance',
    'gate': 'gateio',
    'okex': 'okex',
    'mexc': 'mexc',
    'hb': 'huobi'
}


async def get_currency():
    result = {}
    currency = []
    websea_instance = AApi(token='cb95edcac135b5a28ed76233abca5b00', secret_key='t8leukegp3t487kzj9xf')
    re = await websea_instance.symbols()
    res = re['result']
    for i in res:
        if i['symbol'].split('-')[0] in off_spot_currency:
            continue
        currency.append(i['symbol'].split('-')[0])
        result[i['symbol'].split('-')[0]] = {}
        result[i['symbol'].split('-')[0]]['huobi'] = []
        result[i['symbol'].split('-')[0]]['binance'] = []
        result[i['symbol'].split('-')[0]]['gateio'] = []
        result[i['symbol'].split('-')[0]]['okex'] = []
        result[i['symbol'].split('-')[0]]['websea'] = []
        result[i['symbol'].split('-')[0]]['mexc'] = []
        result[i['symbol'].split('-')[0]]['bitget'] = []
    return currency, result


async def gate_status_v4(currency):
    '''
    delisted : 0表示未下架，1表示已经下架
    withdraw_disabled : 0表示未暂停提现，1表示已经暂停提现
    withdraw_delayed : 0表示未提现没有延迟，1表示提现存在延迟
    deposit_disabled : 0表示未暂停充值，1表示已经暂停充值
    trade_disabled : 0表示未暂停交易，1表示已经暂停交易
    :return:
    '''
    datas = {}
    res = await gateio_instance.currency()
    for i in res:
        k = i['currency']
        if k in ['GTC', 'HERO']:
            continue
        if k == 'GITCOIN':
            k = 'GTC'
        if k == 'DOG':
            k = 'DOGESWAP'
        value = 1
        if i['delisted'] == 1:
            value = '下架'
        elif i['trade_disabled'] == 1:
            value = '暂停交易'
        elif i['withdraw_disabled'] == 1:
            value = 0
        if k in currency:
            if k == 'UNI':
                datas['UNISWAP'] = value
            else:
                datas[k] = value
    return datas


async def get_gate_v4_fee(currency, result):
    datas = await gate_status_v4(currency)
    chain_name = gate_chain_name
    withdraw = await gateio_instance.withdraw()
    gate_cu = []
    for i in withdraw:
        curr = i['currency']
        gate_cu.append(curr)
        if curr in currency:
            try:
                for key, value in i['withdraw_fix_on_chains'].items():
                    if datas.get(curr, 0) == 1:
                        result[curr]['gateio'].append(
                            chain_name.get(key, key).upper() + '提币:' + i['withdraw_percent'] + '+' + str(
                                value) + curr + '(' + str(round(
                                float(value) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)' + ' | 充币:' + str(
                                i['deposit']))
                    else:
                        result[curr]['gateio'] = '暂停提币'
            except:
                if datas.get(curr, 0) == 1:
                    result[curr]['gateio'].append(
                        chain_name.get(curr, curr).upper() + '提币:' + i['withdraw_percent'] + '+' + str(
                            i['withdraw_fix']) + curr + '(' + str(round(
                            float(i['withdraw_fix']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)' + ' | 充币:' + str(
                            i['deposit']))
                else:
                    result[curr]['gateio'] = '暂停提币'
    for i in currency:
        if i not in gate_cu:
            result[i]['gateio'] = '无当前币种'
    for k, v in result.items():
        if v['gateio'] == []:
            result[k]['gateio'] = '无当前币种'


async def get_binance_fee(currency, result):
    chain_name = balance_chain_name
    res = await bn_instance.currency()
    bn_cu = []
    for re in res:
        curr = re['coin']
        # if curr == '1000SATS':
        #     curr = 'SATS'
        bn_cu.append(curr)
        if curr in currency:
            for net in re['networkList']:
                if net['withdrawEnable'] == True:
                    chain = net['network']
                    if '(' in net['name'] and ')' in net['name']:
                        chain = net['name'].split("(")[1].split(")")[0]
                    elif '-' in net['name']:
                        chain = net['name'].split("-")[-1]
                    chain = chain_name.get(chain, chain).upper()
                    if curr == 'SATS':
                        fee = str(float(net['withdrawFee']) * 1000)
                        result[curr]['binance'].append(chain + '提币:' + fee + curr + '(' + str(
                            round(float(fee) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                    else:
                        result[curr]['binance'].append(chain + '提币:' + net['withdrawFee'] + curr + '(' + str(
                            round(float(net['withdrawFee']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                else:
                    pass
    for i in currency:
        if i not in bn_cu:
            result[i]['binance'] = '无当前币种'


async def get_huobi_fee(currency, result):
    chain_name = huobi_chain_name
    re = await huobi_instance.currency()
    results = re['data']
    huobi_cu = []
    for re in results:
        curr = re['currency'].upper()
        huobi_cu.append(curr)
        if curr in currency:
            if re['instStatus'] == 'normal':
                for i in re['chains']:
                    if i['withdrawStatus'] == 'allowed':
                        try:
                            chain = chain_name.get(i['displayName'], i['displayName']).upper()
                            result[curr]['huobi'].append(
                                chain + '提币:' + i['transactFeeWithdraw'] + curr + '(' + str(
                                    round(float(i['transactFeeWithdraw']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                        except:
                            if curr in i['displayName']:
                                chain = chain_name.get(curr, curr).upper()
                                try:
                                    result[curr]['huobi'].append(
                                        chain + '提币:' + i['transactFeeWithdraw'] + curr + '(' + str(
                                            round(float(i['transactFeeWithdraw']) * CURRENCY_RATE.get(curr, 0),
                                                  2)) + 'u)')
                                except:
                                    result[curr]['huobi'].append(
                                        chain + '提币:' + i['minTransactFeeWithdraw'] + curr + '(' + str(
                                            round(float(i['minTransactFeeWithdraw']) * CURRENCY_RATE.get(curr, 0),
                                                  2)) + 'u)')
                            else:
                                chain = chain_name.get(i['displayName'], i['displayName']).upper()
                                result[curr]['huobi'].append(
                                    chain + '提币:' + i['transactFeeWithdraw'] + curr + '(' + str(
                                        round(float(i['transactFeeWithdraw']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                    else:
                        pass
            else:
                result[curr]['huobi'] = '已下架'
    for i in currency:
        if i not in huobi_cu:
            result[i]['huobi'] = '无当前币种'


async def get_okex_v5_fee(currency, result):
    chain_name = okex_chain_name
    res = await okex_instance.currency()
    ok_cu = []
    for re in res['data']:
        curr = re['ccy']
        ok_cu.append(curr)
        if curr in currency:
            chain = re['chain']
            if '-' in re['chain']:
                chain = chain.split('-')[1]
            chain = chain_name.get(chain, chain).upper()
            if re['canWd'] == True:
                result[curr]['okex'].append(
                    chain + '提币:' + re['minFee'] + '-' + re['maxFee'] + curr + '(' + str(
                        round(float(re['minFee']) * CURRENCY_RATE.get(curr, 0), 2)) + '-' + str(
                        round(float(re['maxFee']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
            else:
                pass
    for i in currency:
        if i not in ok_cu:
            result[i]['okex'] = '无当前币种'


async def bitget_fee(currency, result):
    chain_name = bitget_chain_name
    res = await bitget_instance.currency()
    bitget_cu = []
    for i in res['data']:
        curr = i['coin']
        bitget_cu.append(curr)
        if curr in currency:
            for net in i['chains']:
                chain = chain_name.get(net['chain'], net['chain']).upper()
                if net['withdrawable'] == "true":
                    result[curr]['bitget'].append(chain + '提币:' + str(net['withdrawFee']) + curr + '(' + str(
                        round(float(net['withdrawFee']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                else:
                    pass
    for i in currency:
        if i not in bitget_cu:
            result[i]['bitget'] = '无当前币种'
    for k, v in result.items():
        if v['bitget'] == []:
            result[k]['bitget'] = '无当前币种'


async def get_mexc_fee(currency, result):
    chain_name = mxc_chain_name
    coin_list = await mexc_instance.currency()
    mexc_cu = []
    for i in coin_list['data']:
        curr = i['currency']
        mexc_cu.append(curr)
        if curr in currency:
            for net in i['coins']:
                chain = chain_name.get(net['chain'], net['chain']).upper()
                if '(' in chain and ')' in chain:
                    chain = chain.split('(')[-1].split(')')[0].upper()
                if net['is_withdraw_enabled'] == True:
                    result[curr]['mexc'].append(chain + '提币:' + str(net['fee']) + curr + '(' + str(
                        round(float(net['fee']) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                else:
                    pass
    for i in currency:
        if i not in mexc_cu:
            result[i]['mexc'] = '无当前币种'
    for k, v in result.items():
        if v['mexc'] == []:
            result[k]['mexc'] = '无当前币种'


async def get_websea_fee(currency, result):
    chain_name = websea_chain_name
    while True:
        try:
            re = await A_INTERFACES().currency_list(symbol=None)
            res = re['result']
            break
        except Exception as error:
            print(f'获取充提接口失败：{traceback.format_exc()}')
            time.sleep(5)
    abc_cu = []
    for re in res:
        curr = re['name'].upper()
        abc_cu.append(curr)
        if curr in currency:
            for c_token in re['currency_token']:
                usdt_price = 7.23
                chain = chain_name.get(c_token['chain_name'], c_token['chain_name']).upper()
                if c_token['is_take'] == 1:
                    fee = None
                    if c_token['choose_take_fee_type'] == 1:
                        fee = float(c_token['service_fee']) * float(c_token['take_out_ratio'])
                    elif c_token['choose_take_fee_type'] == 2:
                        try:
                            fee = float(c_token['take_fee_quota_one']) / (CURRENCY_RATE.get(curr, 0) * usdt_price) * \
                                  float(c_token['take_out_ratio'])
                        except:
                            fee = float(c_token['service_fee']) * float(c_token['take_out_ratio'])
                    elif c_token['choose_take_fee_type'] == 3:
                        take_num = float(c_token['take_amount_min'])
                        fee = take_num * float(c_token['takeout_fee_rate_one']) * float(c_token['take_out_ratio'])
                    elif c_token['choose_take_fee_type'] == 4:
                        # 火币取不到,就取 CNY额度. 没有设置额度或者没有价格计算不出来 就取固定数量
                        hb_fee = await huobi_instance.currency(currency=curr)
                        if hb_fee['data']:
                            for hb_chain in hb_fee['data'][0]['chains']:
                                if hb_chain.get('baseChainProtocol') == c_token['base_chain_protocol'] or \
                                        hb_chain['displayName'] == c_token['notes']:
                                    fee = hb_chain['transactFeeWithdraw']
                        if not fee:
                            try:
                                fee = float(c_token['take_fee_quota_one']) / (CURRENCY_RATE.get(curr, 0) * usdt_price) * \
                                      float(c_token['take_out_ratio'])
                            except:
                                fee = float(c_token['service_fee']) * float(c_token['take_out_ratio'])
                    if fee:
                        result[curr]['websea'].append(chain + '提币:' + str(fee) + curr + '(' + str(
                            round(float(fee) * CURRENCY_RATE.get(curr, 0), 2)) + 'u)')
                else:
                    result[curr]['websea'].append(chain + '暂停提币')
    for i in currency:
        if i not in abc_cu:
            result[i]['websea'] = '无当前币种'


async def get_hedge_config():
    websea_hedge = {}
    hedge_config = await Hedge_MysqlSession.fetch_all('select * from hedge_config')
    for config in hedge_config:
        config_li = json.loads(config[1])
        datas = []
        for ex, value in config_li['exchanges'].items():
            if float(value['percent']) != 0:
                datas.append(ex)
        websea_hedge[config[0]] = datas
    return websea_hedge


async def main():
    await heartbeat.i_live_well("外部交易所充提手续费", 60 * 17 * 2, 66)
    currency, result = await get_currency()
    for i in set(currency):
        try:
            price = list((await price_redis_db.async_connection.hgetall(i + '-USDT')).values())
            price = float(price[0])
        except:
            price = ''
        if price:
            CURRENCY_RATE[i] = price
    print(CURRENCY_RATE)
    await get_mexc_fee(currency, result)
    await get_gate_v4_fee(currency, result)
    await get_huobi_fee(currency, result)
    await get_okex_v5_fee(currency, result)
    await get_binance_fee(currency, result)
    await get_websea_fee(currency, result)
    await bitget_fee(currency, result)
    print(result)
    websea_hedge = await get_hedge_config()
    re = await G_MysqlSession.fetch_all('select * from withdraw_deposit_fee')
    datas = {}
    for i in re:
        datas[i[0]] = {'websea_hedge': i[1], 'huobi': i[2], 'binance': i[3], 'okex': i[4], 'gateio': i[5], 'mexc': i[6],
                       'websea': i[7], 'bitget': i[8]}
    message_error = f'！！充提手续费异常变动，注意提币费用(对冲交易所):\n'
    for k, v in result.items():
        valuse = ''
        hedge_li = websea_hedge.get(k, [])
        for i, j in v.items():
            try:
                if str(datas[k][i]) != str(j):
                    for hedge in hedge_li:
                        exchange = hedge_exchange.get(hedge, hedge)
                        if i == exchange and '无当前币种' not in str(datas[k][i]) and '无当前币种' not in str(j):
                            list_ini = datas[k][i].split('[')[1].split(']')[0].replace("'", "").split(',')
                            for index in range(len(list_ini)):
                                old = float(str(list_ini[index]).split('(')[1].split('u')[0])
                                new = float(str(j[index]).split('(')[1].split('u')[0])
                                if old != 0:
                                    if hedge == 'gateio':
                                        gate_fee_pec_old = float(str(datas[k][i]).split(':')[1].split('%')[0])
                                        gate_fee_pec_new = float(str(j).split(':')[1].split('%')[0])
                                        if gate_fee_pec_new != gate_fee_pec_old:
                                            message_error += f'【{k}】{i} 手续费: {str(datas[k][i])} --> {str(j)} ' \
                                                             f'对冲: {hedge}\n'
                                            break
                                    mul = round(new / old, 2)
                                    if mul <= 0.5 or mul >= 1.5 and new >= 15:
                                        message_error += f'【{k}】{i} 手续费: {str(datas[k][i])} --> {str(j)} ' \
                                                         f'对冲: {hedge}\n'
                                        break

            except Exception as e:
                # print(f'{cu_time}程序异常---->', traceback.format_exc())
                sql = f'''INSERT ignore INTO withdraw_deposit_fee (currency,websea_hedge,huobi,binance,okex,gateio,mexc,websea,bitget) VALUES ("{k}","{hedge_li}","{v['huobi']}","{v['binance']}","{v['okex']}","{v['gateio']}","{v['mexc']}","{v['websea']}","{v['bitget']}")'''
                await G_MysqlSession.insert(sql)
            valuse += f'{i}="{j}",'
        valuse += f'websea_hedge="{hedge_li}"'
        update_sql = f'''UPDATE withdraw_deposit_fee SET {valuse} WHERE currency='{k}' '''
        await G_MysqlSession.insert(update_sql)
    if message_error != f'！！充提手续费异常变动，注意提币费用(对冲交易所):\n':
        pass
        # await send_telegram_async(message_error, 'dw_info')
    await heartbeat.i_live_well("外部交易所充提手续费", 60 * 17 * 2, 66)


async def get_fee_list():
    sql = 'select currency,websea_hedge,gateio from withdraw_deposit_fee'
    re = await G_MysqlSession.fetch_all(sql)
    for i in re:
        if '提币:0%' not in i[2] and '无当前币种' not in i[2]:
            print(f'【{i[0]}】{i[1]} 手续费: {i[2]}')


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
