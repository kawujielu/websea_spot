import os, sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exchanges.restful_api.binance import bn_instance
from exchanges.restful_api.gateio import gateio_instance
import asyncio
from libs.send_tglegram_msg import send_telegram_async


async def bn_margin_account():
    bn_msg = []
    margin_account = []
    margin_account_data = await bn_instance.margin_account()
    for info in margin_account_data['userAssets']:
        coin_details = {}
        if float(info['borrowed']) > 0:
            coin_details['asset'] = info['asset']
            coin_details['free'] = info['free']
            coin_details['locked'] = info['locked']
            coin_details['borrowed'] = info['borrowed']
            coin_details['interest'] = info['interest']
            coin_details['netAsset'] = info['netAsset']
            margin_account.append(coin_details)
    print(margin_account)
    for info in margin_account:
        bn_msg.append(f'bn => {info["asset"]} 借入: {info["borrowed"]}')
    print(bn_msg)
    return bn_msg


async def get_gate_account(account):
    coin_details = {}
    coin_details['available'] = account['available']
    coin_details['freeze'] = account['freeze']
    coin_details['borrowed'] = account['borrowed']
    coin_details['negative_liab'] = account['negative_liab']
    coin_details['futures_pos_liab'] = account['futures_pos_liab']
    coin_details['equity'] = account['equity']
    coin_details['total_freeze'] = account['total_freeze']
    coin_details['total_liab'] = account['total_liab']
    return coin_details


async def gate_margin_account():
    gate_msg = []
    margin_account = []
    unified_accounts = await gateio_instance.unified_accounts()
    for coin, account in unified_accounts['balances'].items():
        if float(account['borrowed']) > 0:
            coin_details = await get_gate_account(account)
            coin_details['currency'] = coin
            margin_account.append(coin_details)
    print(margin_account)
    for info in margin_account:
        gate_msg.append(f'gate => {info["currency"]} 借入: {info["borrowed"]}')
    print(gate_msg)
    return gate_msg


async def main():
    bn_msg = await bn_margin_account()
    gate_msg = await gate_margin_account()
    msg = '\n'.join(bn_msg + gate_msg)
    cu_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if msg:
        msg = '外部交易所借贷尚未归还，注意及时处理（1次/10分钟）:\n' + msg
        print(f'{cu_time} ==> loan msg {msg}')
        msg_len = len(msg)
        for i in range(0, msg_len, 4000):
            content = msg[i:i + 4000]
            await send_telegram_async(content, 'yk_warning')


if __name__ == '__main__':
    asyncio.run(main())
