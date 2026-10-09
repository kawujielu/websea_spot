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
from libs.chain_name_config import websea_chain_name, mxc_chain_name, gate_chain_name, huobi_chain_name, \
    okex_chain_name, bitget_chain_name, balance_chain_name
from libs.delisting_currency import off_spot_currency
from loguru import logger

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
        result[i['symbol'].split('-')[0]]['mexc'] = []
        result[i['symbol'].split('-')[0]]['websea'] = []
        result[i['symbol'].split('-')[0]]['bitget'] = []
    return currency, result


async def websea(currency, result):
    chain_name = websea_chain_name
    while True:
        try:
            re = await A_INTERFACES().currency_list(symbol=None)
            res = re['result']
            break
        except Exception as error:
            logger.error(f'获取充提接口失败：{traceback.format_exc()}')
            time.sleep(5)
    abc_cu = []
    for re in res:
        curr = re['name'].upper()
        abc_cu.append(curr)
        if curr in currency:
            for i in re['currency_token']:
                if i['status'] == 2:
                    continue
                chain = chain_name.get(i['chain_name'], i['chain_name']).upper()
                if i['is_take'] == 1 and i['is_recharge'] == 1:
                    result[curr]['websea'].append(chain + '|正常')
                elif i['is_take'] == 0 and i['is_recharge'] == 0:
                    result[curr]['websea'].append(chain + '|暂停充提')
                elif i['is_recharge'] == 0:
                    result[curr]['websea'].append(chain + '|暂停充币')
                elif i['is_take'] == 0:
                    result[curr]['websea'].append(chain + '|暂停提币')
            if len(re['currency_token']) == 0:
                chain = chain_name.get(re['name'], re['name']).upper()
                if re['is_take'] == 1 and re['is_recharge'] == 1:
                    result[curr]['websea'].append(chain + '|正常')
                elif re['is_take'] == 0 and re['is_recharge'] == 0:
                    result[curr]['websea'].append(chain + '|暂停充提')
                elif re['is_recharge'] == 0:
                    result[curr]['websea'].append(chain + '|暂停充币')
                elif re['is_take'] == 0:
                    result[curr]['websea'].append(chain + '|暂停提币')
    for i in currency:
        if i not in abc_cu:
            result[i]['websea'] = '无当前币种'


async def mexc(currency, result):
    # /api/v3/capital/config/getall 改成私有接口了，暂时不对接
    return
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
                    chain = chain.split('(')[-1].split(')')[0]
                    chain = chain_name.get(chain, chain).upper()
                if net['is_deposit_enabled'] == True and net['is_withdraw_enabled'] == True:
                    result[curr]['mexc'].append(chain + '|正常')
                elif net['is_deposit_enabled'] == False and net['is_withdraw_enabled'] == False:
                    result[curr]['mexc'].append(chain + '|暂停充提')
                elif net['is_deposit_enabled'] == False:
                    result[curr]['mexc'].append(chain + '|暂停充币')
                elif net['is_withdraw_enabled'] == False:
                    result[curr]['mexc'].append(chain + '|暂停提币')
    for i in currency:
        if i not in mexc_cu:
            result[i]['mexc'] = '无当前币种'


async def gate(currency, result):
    '''
        delisted : 0表示未下架，1表示已经下架
        withdraw_disabled : 0表示未暂停提现，1表示已经暂停提现
        withdraw_delayed : 0表示未提现没有延迟，1表示提现存在延迟
        deposit_disabled : 0表示未暂停充值，1表示已经暂停充值
        trade_disabled : 0表示未暂停交易，1表示已经暂停交易
        :return:
        '''
    results = await gateio_instance.currency()
    chain_name = gate_chain_name
    gate_cu = []
    for re in results:
        curr = re['currency'].split('_')[0].upper()
        gate_cu.append(curr)
        if curr in currency:
            for chain_info in re["chains"]:
                chain = chain_name.get(chain_info['name'], chain_info['name']).upper()
                if chain_info['withdraw_disabled'] and chain_info['deposit_disabled']:
                    result[curr]['gateio'].append(chain + '|暂停充提')
                elif chain_info['withdraw_disabled']:
                    result[curr]['gateio'].append(chain + '|暂停提币')
                elif chain_info['deposit_disabled']:
                    result[curr]['gateio'].append(chain + '|暂停充币')
                else:
                    result[curr]['gateio'].append(chain + '|正常')
    for i in currency:
        if i not in gate_cu:
            result[i]['gateio'] = '无当前币种'
    for k, v in result.items():
        if v['gateio'] == []:
            result[k]['gateio'] = '无当前币种'


async def huobi(currency, result):
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
                    if i['withdrawStatus'] == 'allowed' and i['depositStatus'] == 'allowed':
                        try:
                            chain = chain_name.get(i['displayName'], i['displayName']).upper()
                            result[curr]['huobi'].append(chain + '|正常')
                        except:
                            if curr in i['displayName']:
                                chain = chain_name.get(curr, curr).upper()
                                result[curr]['huobi'].append(chain + '|正常')
                            else:
                                if curr == 'HT':
                                    result[curr]['huobi'].append('HRC20' + '|正常')
                                else:
                                    chain = chain_name.get(i['displayName'], i['displayName'])
                                    result[curr]['huobi'].append(chain + '|正常')
                    elif i['depositStatus'] == 'prohibited' and i['withdrawStatus'] == 'prohibited':
                        try:
                            chain = chain_name.get(i['displayName'], i['displayName']).upper()
                            result[curr]['huobi'].append(chain + '|暂停充提')
                        except:
                            if curr in i['displayName']:
                                chain = chain_name.get(curr, curr).upper()
                                result[curr]['huobi'].append(chain + '|暂停充提')
                            else:
                                if curr == 'HT':
                                    result[curr]['huobi'].append('HRC20' + '|暂停充提')
                                else:
                                    chain = chain_name.get(i['displayName'], i['displayName'])
                                    result[curr]['huobi'].append(chain + '|暂停充提')
                    elif i['depositStatus'] == 'prohibited':
                        try:
                            chain = chain_name.get(i['displayName'], i['displayName']).upper()
                            result[curr]['huobi'].append(chain + '|暂停充币')
                        except:
                            if curr in i['displayName']:
                                chain = chain_name.get(curr, curr).upper()
                                result[curr]['huobi'].append(chain + '|暂停充币')
                            else:
                                if curr == 'HT':
                                    result[curr]['huobi'].append('HRC20' + '|暂停充币')
                                else:
                                    chain = chain_name.get(i['displayName'], i['displayName'])
                                    result[curr]['huobi'].append(chain + '|暂停充币')
                    elif i['withdrawStatus'] == 'prohibited':
                        try:
                            chain = chain_name.get(i['displayName'], i['displayName']).upper()
                            result[curr]['huobi'].append(chain + '|暂停提币')
                        except:
                            if curr in i['displayName']:
                                chain = chain_name.get(curr, curr).upper()
                                result[curr]['huobi'].append(chain + '|暂停提币')
                            else:
                                if curr == 'HT':
                                    result[curr]['huobi'].append('HRC20' + '|暂停提币')
                                else:
                                    chain = chain_name.get(i['displayName'], i['displayName'])
                                    result[curr]['huobi'].append(chain + '|暂停提币')
            else:
                result[curr]['huobi'] = '已下架'
    for i in currency:
        if i not in huobi_cu:
            result[i]['huobi'] = '无当前币种'


async def balance(currency, result):
    chain_name = balance_chain_name
    res = await bn_instance.currency()
    bn_cu = []
    for re in res:
        curr = re['coin']
        # if curr == '1000SATS':
        #     curr = 'SATS'
        bn_cu.append(curr)
        # if re['coin'] in currency + ['1000SATS']:
        if re['coin'] in currency:

            for net in re['networkList']:
                chain = net['network']
                if '(' in net['name'] and ')' in net['name']:
                    chain = net['name'].split("(")[1].split(")")[0]
                elif '-' in net['name']:
                    chain = net['name'].split("-")[-1]
                chain = chain_name.get(chain, chain).upper()
                if net['depositEnable'] == True and net['withdrawEnable'] == True:
                    result[curr]['binance'].append(chain + '|正常')
                elif net['depositEnable'] == False and net['withdrawEnable'] == False:
                    result[curr]['binance'].append(chain + '|暂停充提')
                elif net['depositEnable'] == False:
                    result[curr]['binance'].append(chain + '|暂停充币')
                elif net['withdrawEnable'] == False:
                    result[curr]['binance'].append(chain + '|暂停提币')
    for i in currency:
        if i not in bn_cu:
            result[i]['binance'] = '无当前币种'


async def okex(currency, result):
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
            if re['canWd'] == True and re['canDep'] == True:
                result[curr]['okex'].append(chain + '|正常')
            elif re['canDep'] == False and re['canWd'] == False:
                result[curr]['okex'].append(chain + '|暂停充提')
            elif re['canDep'] == False:
                result[curr]['okex'].append(chain + '|暂停充币')
            elif re['canWd'] == False:
                result[curr]['okex'].append(chain + '|暂停提币')
    for i in currency:
        if i not in ok_cu:
            result[i]['okex'] = '无当前币种'


async def bitget(currency, result):
    chain_name = bitget_chain_name
    res = await bitget_instance.currency()
    bitget_cu = []
    for i in res['data']:
        curr = i['coin']
        bitget_cu.append(curr)
        if curr in currency:
            for net in i['chains']:
                chain = chain_name.get(net['chain'], net['chain']).upper()
                if net['rechargeable'] == "true" and net['withdrawable'] == "true":
                    result[curr]['bitget'].append(chain + '|正常')
                elif net['rechargeable'] == "false" and net['withdrawable'] == "false":
                    result[curr]['bitget'].append(chain + '|暂停充提')
                elif net['rechargeable'] == "false":
                    result[curr]['bitget'].append(chain + '|暂停充币')
                elif net['withdrawable'] == "false":
                    result[curr]['bitget'].append(chain + '|暂停提币')
    for i in currency:
        if i not in bitget_cu:
            result[i]['bitget'] = '无当前币种'


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
    currency, result = await get_currency()
    await gate(currency, result)
    await huobi(currency, result)
    await okex(currency, result)
    await mexc(currency, result)
    await balance(currency, result)
    await websea(currency, result)
    await bitget(currency, result)
    websea_hedge = await get_hedge_config()
    re = await G_MysqlSession.fetch_all('select * from withdraw_deposit')
    datas = {}
    for i in re:
        datas[i[0]] = {'websea_hedge': i[1], 'huobi': i[2], 'binance': i[3], 'okex': i[4], 'gateio': i[5], 'mexc': i[6],
                       'websea': i[7], 'bitget': i[7]}
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    message = f'{cu_time} 充提:\n'
    for k, v in result.items():
        valuse = ''
        hedge_li = websea_hedge.get(k, [])
        history_list, new_list, li = [], [], []
        for i, j in v.items():
            try:
                if str(datas[k][i]) != str(j):
                    try:
                        list_ini = datas[k][i].split('[')[1].split(']')[0].replace("'", "").split(',')
                        for ini in range(len(list_ini)):
                            history = list_ini[ini].replace(' ', '')
                            new = j[ini].replace(' ', '')
                            if history != new:
                                history_list.append(history)
                                new_list.append(new)
                        for new in new_list:
                            if new in history_list:
                                li.append(new)
                        if len(li) != len(history_list):
                            message += f' 交易所: {i}  币种: {k} 状态: {str(",".join(history_list))} --> {str(",".join(new_list))} Websea状态: {v.get("websea")}'
                            for hedge in hedge_li:
                                if i == hedge:
                                    exchange = hedge_exchange.get(hedge, hedge)
                                    message += f' | 对冲交易所: {hedge}（{v.get(exchange)}）'
                            message = message + '\n'
                    except:
                        message += f' 交易所: {i}  币种: {k} 状态: {str(datas[k][i])} --> {str(j)} Websea状态: {v.get("websea")}\n'
                        for hedge in hedge_li:
                            if i == hedge:
                                exchange = hedge_exchange.get(hedge, hedge)
                                message += f' | 对冲交易所: {hedge}（{v.get(exchange)}）'
                        message = message + '\n'
            except Exception as e:
                logger.error(f'{cu_time}程序异常---->', traceback.format_exc())
                sql = f'''INSERT ignore INTO withdraw_deposit (currency,websea_hedge,huobi,binance,okex,gateio,mexc,websea,bitget) VALUES ("{k}","{hedge_li}","{v['huobi']}","{v['binance']}","{v['okex']}","{v['gateio']}","{v['mexc']}","{v['websea']}","{v['bitget']}")'''
                await G_MysqlSession.insert(sql)
            valuse += f'{i}="{j}",'
        valuse += f'websea_hedge="{hedge_li}"'
        update_sql = f'''UPDATE withdraw_deposit SET {valuse} WHERE currency='{k}' '''
        await G_MysqlSession.insert(update_sql)
    if message != f'{cu_time} 充提:\n':
        pass
        # await send_telegram_async(message, 'dw_info')
    await heartbeat.i_live_well("外部交易所充提状态", 60 * 17 * 2, 66)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
