from exchanges.restful_api.binance import bn_instance
from exchanges.restful_api.gateio import gateio_instance
from exchanges.restful_api.abc_interfaces2 import A_INTERFACES
import asyncio
import datetime
import time


async def main():
    # all_assets = await bn_instance.margin_allAssets()
    # print(all_assets)
    # start = '2023-11-11 00:00:00'
    # end = '2023-12-13 00:00:00'
    # start = int(datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S').timestamp()) * 1000
    # end = int(datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S').timestamp()) * 1000
    # print(start)
    # margin_loan = await bn_instance.margin_loan_list(currency='BTC', startTime=start, endTime=end)
    # print(margin_loan)
    # margin_repay = await bn_instance.margin_repay_list(currency='BTC')
    # print(margin_repay)
    # margin_transfer = await bn_instance.margin_transfer_list(currency='USDT')
    # print(margin_transfer)
    margin_account = await bn_instance.margin_account()
    print(margin_account)
    # max_borrowable = await bn_instance.max_borrowable(currency='BTC')
    # print(max_borrowable)
    # res = await bn_instance.margin_loan(currency='BTC', amount='0.0002')
    # print(res)
    # res = await bn_instance.margin_repay(currency='BTC', amount='0.0002')
    # print(res)
    # res = await bn_instance.margin_transfer(currency='USDT', amount=10, transfer_type=1)
    # print(res)
    # res = await bn_instance.interest_history(currency='BTC')
    # print(res)
    # await find_account()
    # spot_wallet = await bn_instance.wallet()
    # print(list(spot_wallet.keys()))
    # leverage_bracket = await bn_instance.leverage_bracket()
    # print(leverage_bracket)
    # margin_account = await bn_instance.margin_account()
    # coins = []
    # for info in margin_account['userAssets']:
    #     coins.append(info['asset'])
    # print(coins)
    # await find_account()


async def find_account():
    search_coin = 'BTC'
    res = await bn_instance.vip_loanable_data(currency=search_coin)
    print(res)
    # cross_margin_data = await bn_instance.cross_margin_data(currency=search_coin)
    # cross_margin_data = cross_margin_data[0]
    # max_borrowable = await bn_instance.max_borrowable(currency=search_coin)
    # max_transferble = await bn_instance.max_transferble(currency=search_coin)
    # spot_wallet = await bn_instance.wallet()
    # margin_account = await bn_instance.margin_account()
    # margin_hourly_rate = await bn_instance.margin_hourly_rate(currency=search_coin)
    # coin_details = {'borrowable': cross_margin_data['borrowable'], 'transferIn': cross_margin_data['transferIn'],
    #                 'dailyInterest': cross_margin_data['dailyInterest'],
    #                 'yearlyInterest': cross_margin_data['yearlyInterest'],
    #                 'borrowLimit': cross_margin_data['borrowLimit'],
    #                 'maxBorrow': max_borrowable['amount'],
    #                 'maxTransfer': max_transferble['amount']}
    # for info in margin_account['userAssets']:
    #     if info['asset'] == search_coin:
    #         coin_details['free'] = info['free']
    #         coin_details['locked'] = info['locked']
    #         coin_details['borrowed'] = info['borrowed']
    #         coin_details['interest'] = info['interest']
    #         coin_details['netAsset'] = info['netAsset']
    # coin_details['spotWallet'] = spot_wallet.get(search_coin, 0)
    # coin_details['hourlyInterest'] = margin_hourly_rate[0]['nextHourlyInterestRate']
    print(coin_details)


async def gateio_api_test():
    '''
    {'borrowable': True, 'transferIn': True, 'dailyInterest': '0.00003141', 'yearlyInterest': '0.0114641', 'borrowLimit': '60', 'maxBorrow': '0.00091484', 'maxTransfer': '0', 'free': '0', 'locked': '0', 'borrowed': '0', 'interest': '0', 'netAsset': '0', 'spotWallet': 0.10215481, 'hourlyInterest': '0.000044'}
    '''
    search_coin = 'BNSX'
    coin_details = {}
    unified_accounts = await gateio_instance.unified_accounts(currency=search_coin)
    print(unified_accounts)
    unified_account_mode = await gateio_instance.unified_account_mode()
    unified_borrowable = await gateio_instance.unified_borrowable(currency=search_coin)
    unified_transferable = await gateio_instance.unified_transferable(currency=search_coin)
    wallet = await gateio_instance.wallet(currency=search_coin)
    for currency, account in unified_accounts['balances'].items():
        coin_details['currency'] = currency
        coin_details['available'] = account['available']
        coin_details['freeze'] = account['freeze']
        coin_details['borrowed'] = account['borrowed']
        coin_details['negative_liab'] = account['negative_liab']
        coin_details['futures_pos_liab'] = account['futures_pos_liab']
        coin_details['equity'] = account['equity']
        coin_details['total_freeze'] = account['total_freeze']
        coin_details['total_liab'] = account['total_liab']
    coin_details['usdt_futures'] = unified_account_mode['usdt_futures']
    coin_details['cross_margin'] = unified_account_mode['cross_margin']
    coin_details['max_borrowable'] = unified_borrowable['amount']
    coin_details['max_transferable'] = unified_transferable['amount']
    coin_details['spot_wallet'] = wallet.get(search_coin, 0)
    margin_currency = await gateio_instance.margin_currency(currency='BTC')
    coin_details['hourlyInterest'] = margin_currency['rate']
    coin_details['user_max_borrow_amount'] = margin_currency['user_max_borrow_amount']
    coin_details['min_borrow_amount'] = margin_currency['min_borrow_amount']
    coin_details['total_max_borrow_amount'] = margin_currency['total_max_borrow_amount']
    print(coin_details)


async def test_gate_unified():
    unified_accounts = await gateio_instance.unified_accounts()
    print(unified_accounts)
    # search_coin = 'BTC'
    # unified_accounts = await gateio_instance.unified_accounts(currency=search_coin)
    # print(unified_accounts)
    # unified_account_mode = await gateio_instance.unified_account_mode()
    # print(unified_account_mode)
    # unified_borrowable = await gateio_instance.unified_borrowable(currency=search_coin)
    # print(unified_borrowable)
    # unified_transferable = await gateio_instance.unified_transferable(currency=search_coin)
    # print(unified_transferable)
    # wallet = await gateio_instance.wallet(currency=search_coin)
    # print(wallet)
    # unified_loans = await gateio_instance.unified_loans(currency='BTC', amount=0.0001, unified_type='borrow')
    # print(unified_loans)
    # unified_loans_reply = await gateio_instance.unified_loans(currency='BTC', amount=0.0001, unified_type='repay',
    #                                                           repaid_all=True)
    # print(unified_loans_reply)
    # find_unified_loan = await gateio_instance.find_unified_loan(currency='BTC')
    # print(find_unified_loan)
    # unified_loan_records = await gateio_instance.unified_loan_records(currency='BTC')
    # print(unified_loan_records)
    # unified_interest_records = await gateio_instance.unified_interest_records()
    # print(unified_interest_records)

    # coin_details = {}
    # for currency, account in unified_accounts['balances'].items():
    #     coin_details['currency'] = currency
    #     coin_details['available'] = account['available']
    #     coin_details['freeze'] = account['freeze']
    #     coin_details['borrowed'] = account['borrowed']
    #     coin_details['negative_liab'] = account['negative_liab']
    #     coin_details['futures_pos_liab'] = account['futures_pos_liab']
    #     coin_details['equity'] = account['equity']
    #     coin_details['total_freeze'] = account['total_freeze']
    #     coin_details['total_liab'] = account['total_liab']
    # coin_details['usdt_futures'] = unified_account_mode['usdt_futures']
    # coin_details['cross_margin'] = unified_account_mode['cross_margin']
    # coin_details['max_borrowable'] = unified_borrowable['amount']
    # coin_details['max_transferable'] = unified_transferable['amount']
    # coin_details['spot_wallet'] = wallet.get(search_coin, 0)
    # print(coin_details)


def get_hold_list(symbol=None, user_id=None):
    a_interfaces = A_INTERFACES()
    page_size = 20
    fullholdlist, holdlist = [], []
    for page in range(1, 2):
        res = a_interfaces.contract_treaty_fullholdlist(symbol=symbol, user_id=user_id, page_size=page_size, page=page)
        for i in res['result']['data']['Data']:
            for j in i['contract']:
                for s, v in j.items():
                    d = {}
                    d['symbol'] = s
                    d['user_id'] = v['user_id']
                    d['side'] = '空仓' if v.get('empty_direction') else '多仓'
                    d['direction'] = v.get('empty_direction', v.get('many_direction', 0))  # 张数
                    d['direction_amount'] = v.get('empty_direction_amount', v.get('many_direction_amount'))  # 个数
                    d['direction_price'] = v.get('empty_direction_price', v.get('many_direction_price'))  # 均价
                    d['multiple'] = v.get('empty_multiple', v.get('many_multiple'))  # 杠杆
                    d['parity'] = v.get('强平价', '')  # 强平价
                    d['profit_loss'] = v.get('profit_loss', '')  # 盈亏
                    d['risk_ratio'] = v.get('risk_ratio', '')  # 风险率
                    d['face_value'] = v.get('face_value', '')  # 面值
                    d['type'] = "全仓"
                    info_time = v.get('empty_time', v.get('many_time'))
                    d['time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info_time)))

                    fullholdlist.append(d)
        if len(res['result']['data']['Data']) < page_size:
            break

    for page in range(1, 2):
        res = a_interfaces.contract_treaty_holdlist(symbol=symbol, user_id=user_id, page_size=page_size, page=page)
        for i in res['result']['data']['Data']:
            for j in i['contract']:
                for s, v in j.items():
                    d = {}
                    d['symbol'] = s
                    d['user_id'] = v['user_id']
                    d['side'] = '空仓' if v.get('empty_direction') else '多仓'
                    d['direction'] = v.get('empty_direction', v.get('many_direction', 0))  # 张数
                    d['direction_amount'] = v.get('empty_direction_amount', v.get('many_direction_amount'))  # 个数
                    d['direction_price'] = v.get('empty_direction_price', v.get('many_direction_price'))  # 均价
                    d['multiple'] = v.get('empty_multiple', v.get('many_multiple'))  # 杠杆
                    d['parity'] = v.get('强平价', '')  # 强平价
                    d['profit_loss'] = v.get('profit_loss', '')  # 盈亏
                    d['risk_ratio'] = v.get('risk_ratio', '')  # 风险率
                    d['face_value'] = v.get('face_value', '')  # 面值
                    d['type'] = "逐仓"
                    info_time = v.get('empty_time', v.get('many_time'))
                    d['time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(info_time)))
                    holdlist.append(d)
        if len(res['result']['data']['Data']) < page_size:
            break
    print(len(holdlist + fullholdlist))
    return holdlist + fullholdlist


def find_userid_futurefee():
    a_interfaces = A_INTERFACES()
    res = A_INTERFACES().userid_futurefee()
    user_ids_0 = res['result']
    print(res)


if __name__ == '__main__':
    asyncio.run(find_account())
    # get_hold_list()
    # find_userid_futurefee()
