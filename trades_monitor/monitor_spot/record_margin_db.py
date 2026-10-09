import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exchanges.restful_api.binance import bn_instance
from exchanges.restful_api.gateio import gateio_instance
import asyncio
from scaffold.mysql import G_MysqlSession
import time

time_flag = 10 * 60


async def insert_margin_db(margin_details):
    for info in margin_details:
        txId = info['txId']
        select_sql = f"select txId from margin_details where txId='{txId}'"
        res = await G_MysqlSession.fetch_all(select_sql)
        if not res:
            info_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['timestamp'] / 1000)))
            insert_sql = "INSERT ignore INTO margin_details (txId,asset,amount,clientTag,interest,principal,status,`timestamp`) " \
                         f"VALUES ('{info['txId']}','{info['asset']}','{info.get('amount')}','{info['clientTag']}'," \
                         f"'{info.get('interest')}','{info['principal']}','{info['status']}','{info_time}')"
            await G_MysqlSession.insert(insert_sql)


async def insert_margin_transfer_db(transfer_details):
    for info in transfer_details:
        txId = info['txId']
        select_sql = f"select txId from transfer_details where txId='{txId}'"
        res = await G_MysqlSession.fetch_all(select_sql)
        if not res:
            info_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['timestamp'] / 1000)))
            insert_sql = "INSERT ignore INTO transfer_details (txId,asset,amount,transFrom,transTo,`type`,status,`timestamp`) " \
                         f"VALUES ('{info['txId']}','{info['asset']}','{info.get('amount')}','{info['transFrom']}'," \
                         f"'{info.get('transTo')}','{info['type']}','{info['status']}','{info_time}')"
            await G_MysqlSession.insert(insert_sql)


async def record_bn(bn_msg):
    margin_loan = await bn_instance.margin_loan_list()
    margin_repay = await bn_instance.margin_repay_list()
    margin_transfer = await bn_instance.margin_transfer_list()
    margin_details = margin_loan['rows'] + margin_repay['rows']
    print(margin_details)
    '''
    {
        "isolatedSymbol": "BNBUSDT",     // 逐仓还款 返回逐仓symbol; 若是全仓不会返回此字段
        "amount": "14.00000000",   // 还款总额
        "asset": "BNB",   
        "interest": "0.01866667",    // 支付的利息
        "principal": "13.98133333",   // 支付的本金
        "status": "CONFIRMED",   //状态: PENDING (等待执行), CONFIRMED (成功还款), FAILED (执行失败);
        "timestamp": 1563438204000,
        "txId": 2970933056
      }
    '''
    for info in margin_loan['rows']:
        if int(time.time()) - int(int(info['timestamp']) / 1000) <= time_flag:
            info_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['timestamp'] / 1000)))
            message = f'bn => txId: {info["txId"]}, 币种：{info["asset"]}, 借入: {info["principal"]}, ' \
                      f'状态: {info["status"]}, 时间: {info_time}'
            bn_msg.append(message)
    for info in margin_repay['rows']:
        if int(time.time()) - int(int(info['timestamp']) / 1000) <= time_flag:
            info_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['timestamp'] / 1000)))
            message = f'bn => txId: {info["txId"]}, 币种: {info["asset"]}, 还款总额: {info["amount"]}, ' \
                      f'本金: {info["principal"]}, 利息: {info["interest"]}, 状态: {info["status"]}, 时间: {info_time}'
            bn_msg.append(message)
    await insert_margin_db(margin_details)
    transfer_details = margin_transfer['rows']
    print(transfer_details)
    await insert_margin_transfer_db(transfer_details)
    return bn_msg


async def insert_unified_loan_details_gate_db(margin_details):
    for info in margin_details:
        loan_id = info['id']
        select_sql = f"select id from gate_unified_loans_details where id='{loan_id}'"
        res = await G_MysqlSession.fetch_all(select_sql)
        if not res:
            create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['create_time'] / 1000)))
            insert_sql = "INSERT ignore INTO gate_unified_loans_details (id,`type`,margin_mode,currency_pair,currency,amount," \
                         "create_time,repayment_type) " \
                         f"VALUES ('{info['id']}','{info['type']}','{info.get('margin_mode')}','{info.get('currency_pair')}'," \
                         f"'{info['currency']}','{info['amount']}','{create_time}','{info['repayment_type']}')"
            await G_MysqlSession.insert(insert_sql)


async def record_gate(gate_msg):
    unified_loan_records = await gateio_instance.unified_loan_records()
    print(unified_loan_records)
    '''
     {'id': 18502056, 
     'type': 'borrow', 
     'repayment_type': 'manual_repay', 
     还款类型 , none - 无还款类型, manual_repay - 手动还款 , auto_repay - 自动还款, cancel_auto_repay - 撤单后自动还款
     'currency': '1CAT', 
     'amount': '40000', 
     'create_time': 1705015542437}
    '''
    for info in unified_loan_records:
        if int(time.time()) - int(int(info['create_time']) / 1000) <= time_flag:
            loan_type = '借入' if info['type'] == 'borrow' else '还款'
            info_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info['create_time'] / 1000)))
            message = f'gate => txId: {info["id"]}, 币种：{info["currency"]}, {loan_type}: {info["amount"]}, ' \
                      f'还款类型: {info["repayment_type"]},  时间: {info_time}'
            gate_msg.append(message)
    await insert_unified_loan_details_gate_db(unified_loan_records)
    return gate_msg


async def main():
    bn_msg, gate_msg = [], []
    await record_bn(bn_msg)
    await record_gate(gate_msg)


if __name__ == '__main__':
    asyncio.run(main())
