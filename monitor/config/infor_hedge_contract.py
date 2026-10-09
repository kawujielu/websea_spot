# coding=utf-8
from pprint import pprint
from config.infor_load import spot_account

START_AMOUNT_OKEX_CON = {}
START_AMOUNT_HUOBI_CON = {}
START_AMOUNT_BIAN_CON = {}
config_con_exchange = {
    'hedge': {
        'bn': {
            'user': 'abc_manager@proton.me',
            'password': 'Quant123...',
            'ccxtname': 'binance',
            'start_amount': {},
            'google_authenticator': {},
            'apikey': spot_account.get('bn_contract', {}),
            'remarks': '未注册',
        },
    }

}

if __name__ =='__main__':
    print(config_con_exchange)