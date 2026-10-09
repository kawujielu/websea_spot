# coding=utf-8
import asyncio, datetime, time, requests

import pandas as pd
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, infor_contract, infor_hedge
from libs import sendmessage, get_time, heartbeat
from config import infor, infor_hedge, monitor, infor_swap
from exchange.restful_api.abc_interfaces import AINTERFACES
from libs.database.getmysql import G_MysqlSession
from pprint import pprint

# 不提示警告
pd.set_option('mode.chained_assignment', None)

spot_id = infor.acc_id
con_id = infor_contract.acc_id_contract
xdc = [infor_hedge.acc_id_xdc]
quant_id = spot_id + con_id
all_id = spot_id + con_id + xdc

TIME = 15  # 分钟
a_interfaces = AINTERFACES()
getTime = get_time.ATime()


async def run():
    message = ""
    ret = await a_interfaces.transferassets()
    if 'code' not in ret.keys():
        for re in ret['result']['data']:
            timearray = int(re['ctime'])
            if timearray > int(time.time()) - TIME * 60:
                currency_name = re['currency_name']
                from_symbol = re['from_symbol']
                to_symbol = re['to_symbol']
                from_user_id = str(re['from_user_id'])
                to_user_id = str(re['to_user_id'])
                operator_name = re['operator_name']
                amount = float(re['amount'])

                ctime = getTime.timestamp_to_timearray(timearray)

                check_status_type = {'1': '待审核', '2': '已通过', '4': '失败', '3': '驳回'}
                check_status = str(re['check_status'])  # 审核状态
                check_note = re['check_note']  # 审核信息
                transfer_status_type = {'1': '成功', '2': '失败', '0': '待转账'}
                transfer_status = str(re['transfer_status'])  # 审核状态
                transfer_errmsg = re['transfer_errmsg']  # 审核信息
                transfer_type = f'合约划转{from_symbol}>>{to_symbol}' if from_symbol and to_symbol else '现货划转' if not from_symbol and not to_symbol else f'未知划转:{from_symbol}>>{to_symbol}'
                msg = ""

                """
                正常：
                1 现货与现货之间的划转
                2 合约与合约之间的划转
                异常：
                3 现货与合约之间的划转
                4 量化账户与非量化账户之间的划转
                保存数据库:
                5 量化账户与xdc账户之间的划转
                """
                # 异常
                if check_status == '2' or transfer_status == '1':
                    if from_user_id in all_id and to_user_id in all_id:
                        if from_user_id in spot_id and to_user_id in con_id:
                            msg = f'异常：现货账户 =》合约账户\n'
                        elif from_user_id in con_id and to_user_id in spot_id:
                            msg = f'异常：合约账户 =》现货账户\n'
                        elif from_user_id in xdc or to_user_id in xdc:
                            if from_user_id in quant_id:
                                msg = "保存到数据库 现货账户 =》xdc\n"
                            elif to_user_id in quant_id:
                                msg = f"异常：合约账户 =》xdc\n"
                    elif from_user_id not in all_id and to_user_id not in all_id:
                        pass
                    else:
                        msg = "异常：量化 & 用户\n"

                elif (check_status == '1' or transfer_status == '0') and (from_user_id in all_id or to_user_id in all_id):
                    msg = '异常：划转状态\n'

                if msg:
                    message += f'{msg}' \
                               f'币种:{currency_name}\n' \
                               f'创建时间:{ctime}\n' \
                               f'操作人:{operator_name}\n' \
                               f'{transfer_type}\n' \
                               f'ID:{from_user_id} =》{to_user_id}\n' \
                               f'数量:{amount}\n' \
                               f'审核状态:{check_status_type[check_status]}\n' \
                               f'转账状态:{transfer_status_type[transfer_status]}\n\n'
                    if "数据库" in msg:
                        sql = f"insert ignore into exchange_transfer (time,symbol,from_id,to_id,amount) " \
                              f"values {(ctime, currency_name, from_user_id, to_user_id, amount)}"
                        await G_MysqlSession.insert_sql(sql=sql)

    if message != '':
        mess = f'{TIME}分钟内资金划转数据\n' + message
        sendmessage.send_telegram_msg(mess, ser='spot_ProfitLoss')


async def spot_run():
    try:
        await run()
        await heartbeat.i_live_well(server='量化账户划转监控', frequency=60 * 60 * 1.1, index=29)
    except Exception as e:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sendmessage.send_telegram_msg(f'{now} | error：量化账户划转 {e}', ser='Alarm')
        print(f'{now} | error : 量化账户划转 -->> {e}')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
