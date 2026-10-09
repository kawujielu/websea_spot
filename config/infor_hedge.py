# coding=utf-8
from pprint import pprint
from config.infor_load import spot_account

# 量化账户对冲:huobi-bian-okex-dc------------------------------------------------------------------------------------------------------------------

START_AMOUNT_HB = {}
START_AMOUNT_BN = {'BTC': 3.36e-06, 'USDT': 8.6905815, 'TRX': 1e-06, 'MANA': 0.0216, 'ZEN': 0.0022622, 'BCH': 0.05212697, 'BUSD': 0.00147775, 'CRV': 0.057372, 'NMR': 0.000376, 'UNI': 0.00826218, 'XEC': 8.96, 'MANTRA': 7451.2}
START_AMOUNT_MXC = {}
START_AMOUNT_BITGET = {}
START_AMOUNT_KRAKEN = {}
START_AMOUNT_GATE = {}
START_AMOUNT_OKEX = {}
START_AMOUNT_ZB = {}
# 手动对冲 币安 火币 子账户
START_AMOUNT_BINANCE_SON1 = {}
START_AMOUNT_HUOBI_SON1 = {}
START_AMOUNT_HUOBI_SON2 = {}
for k, v in START_AMOUNT_OKEX.items():
    START_AMOUNT_BN[k] = START_AMOUNT_BN.get(k, 0) + v
START_AMOUNT_OKEX = {}
# START_AMOUNT_BN['USDT'] += 10000
# 三角套利------------------------------------------------------------------------------------------------------------------

# 跨交易所套利 -------------------------------------------------------------------------------------------------------------


# 币安-火币-子账户---------------------------------------------------------------------------------------------------------------


# 高频交易---------------------------------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------------------------------

# 2021-01-18 理财
FINANCING_AMOUNT = {}

START_AMOUNT_mxc = {}
# ---------------------------------------------------------------------------------------------------------------

config_exchange = {
    'hedge': {
        'hb': {'uid': None,
               'email': None,
               'user': 'abc_manager@proton.me',
               'password': 'Quant123...',
               'api_name': 'HUOBI',
               'exchange': 'huobipro',
               'start_amount': START_AMOUNT_HB,
               'google_authenticator': '',
               'apikey': {'apiKey': "b7e15bdd-bgbfh5tv3f-0bf80824-d95e5",
                          'secret': "4a340036-a21a5241-c8805729-c4b1c"},
               'remarks': '已注册,需要实名认证才能使用',

               },
        'bn': {'uid': None,
               'email': None,
               'user': 'abc_manager@proton.me',
               'password': 'Quant123...',
               'google_authenticator': None,
               'api_name': 'BIAN',
               'exchange': 'binance',
               'start_amount': START_AMOUNT_BN,
               'apikey': spot_account.get('bn', {}),
               'remarks': '未注册',
               },
        'okex': {'uid': None,
                 'email': None, 'user': 'abc_manager@proton.me',
                 'password': 'Quant123...',
                 'api_name': 'OKEX',
                 'exchange': 'okex5',
                 'start_amount': START_AMOUNT_OKEX,
                 'google_authenticator': 'R5A5CC3ZMJ2S44Y4',
                 'apikey': spot_account.get('okex', {}),
                 'remarks': '未注册',
                 },

        'xdc': {'uid': spot_account.get('xdc', {}).get('uid'),
                'email': None,
                'api_name': 'xdc',
                'exchange': 'abc',
                'start_amount': None,
                'apikey': spot_account.get('xdc', {})
                },
        'gateio': {'uid': None,
                   'email': None,
                   'api_name': None,
                   'exchange': 'gateio',
                   'user': 'abc_manager@proton.me',
                   'password': 'Quant123...',
                   'password_fund': 'abc123...',
                   'ccxtname': 'gateio',
                   'google_authenticator': 'AGVQJUNT4EPW2QU2',
                   'start_amount': START_AMOUNT_GATE,
                   'apikey': spot_account.get('gate', {}),
                   'remarks': '未注册',
                   },
        'mxc': {'uid': None,
                'email': None,
                'api_name': None,
                'exchange': 'mexc',
                'user': 'abc_manager@proton.me',
                'password': 'Quant123...',
                'ccxtname': 'mexc',
                'start_amount': START_AMOUNT_MXC,
                'google_authenticator': '4PZ3NFYOE3RFW3GS',
                'apikey': spot_account.get('mxc', {}),
                'remarks': '未注册',
                },
        'bitget': {'uid': None,
                   'email': None,
                   'api_name': None,
                   'exchange': 'bitget',
                   'user': 'abc_manager@proton.me',
                   'password': 'Quant123...',
                   'ccxtname': 'mexc',
                   'start_amount': START_AMOUNT_BITGET,
                   'google_authenticator': None,
                   'apikey': spot_account.get('bitget', {}),
                   'remarks': '未注册',
                   },
        'kraken': {'uid': None,
                   'email': None,
                   'api_name': None,
                   'exchange': 'kraken',
                   'user': 'abc_manager@proton.me',
                   'password': 'Quant123...',
                   'ccxtname': 'kraken',
                   'start_amount': START_AMOUNT_KRAKEN,
                   'google_authenticator': None,
                   'apikey': spot_account.get('kraken', {}),
                   'remarks': '未注册',
                   },
    },

    'triangular_arbitrage': {},
    'trading_strateg': {},
    'fund': {}
}
acc_id_xdc = config_exchange['hedge']['xdc']['uid']

if __name__ == '__main__':
    print(config_exchange['hedge'])
    import ccxt

    api = config_exchange['hedge']['bn']['apikey']
    re = ccxt.binance(api)
    res = re.fetch_balance()
    print(res)

    pass
