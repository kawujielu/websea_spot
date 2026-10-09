from load import load_remote

REMOTE_IP = "10.0.209.181"
libs_account = load_remote.urllib_model("server@{}".format(REMOTE_IP), "/home/server/abclibs/account.py")
libs_config = load_remote.urllib_model("server@{}".format(REMOTE_IP), "/home/server/abclibs/config.py")
libs_dex_config = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/dex_config.py")
libs_price_async = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price_async.py")
DEBUG = libs_config.DEBUG

# 测试环境域名:https://risk.wtest.club/
# token:d5ee2eedfcf7adc285db4967bd86910d
#
# 完整示例: https://risk.wtest.club/api/funds/contract?token=d5ee2eedfcf7adc285db4967bd86910d

if DEBUG:
    account = libs_account.account_test
    spot_account = libs_account.exchange_accounts
    spot_host = "https://exq.wtest.club"
    # contract_host = "https://coq.wtest.club"
    contract_host = "https://coq.wbstests.net"
    token = "d5ee2eedfcf7adc285db4967bd86910d"
    backstage_host = "https://risk.wtest.club/"
    python_v = '/home/ubuntu/miniconda3/envs/monitor/bin/python3.9'
    web_url = 'https://eapi.wtest.club/webApi/market/getSymbolList?legalId=1'
    web_url_perp = ''
    public_host = ''
    volume_ids = [99523, 99526]

else:
    account = libs_account.account
    spot_account = libs_account.exchange_accounts
    spot_host = "https://exqv.websea.work"
    contract_host = "https://coqv.websea.work"
    token = "c1cf4185b2bed317aeb6e6674491fbef"
    backstage_host = "https://riskapi.websea.work/"
    # python_v = '/home/ubuntu/miniconda3/bin/python3'
    python_v = '/home/ubuntu/miniconda3/envs/monitor/bin/python3.9'
    web_url = "https://eapi.websea.com/webApi/market/getSymbolList?legalId=1"
    web_url_perp = "https://capi.websea.com/webApi/market/getSymbolList?legalId=1"
    public_host = 'https://coapi.websea.com'
    volume_ids = [10]

EXCHANGE_CURRENCY_RANAME = {'gateio': {'ZK': 'ZKJ'}}
spec_symbol_rate_map = libs_config.SPEC_SYMBOL_RATE_MAPPING
spec_contract_symbol_rate_map = libs_config.SPEC_CONTRACT_SYMBOL_RATE_MAPPING
if spec_symbol_rate_map.get('gate'):
    spec_symbol_rate_map['gateio'] = spec_symbol_rate_map.pop('gate')


def get_symbol_rate_mapping(symbol_rate_map):
    spec_symbol_rate_mapping = {}
    spec_symbol_rate_mapping_currency = {}
    for ex, v in symbol_rate_map.items():
        spec_symbol_rate_mapping[ex] = {}
        spec_symbol_rate_mapping_currency[ex] = {}
        for symbol, j in v.items():
            abc_currency = symbol.split('-')[0]
            ex_currency = j[0].split('-')[0]
            pr = j[1]
            spec_symbol_rate_mapping[ex][j[0]] = [symbol, 1 / pr]
            spec_symbol_rate_mapping_currency[ex][abc_currency] = {'name': ex_currency, 'pr': pr}
    return spec_symbol_rate_mapping, spec_symbol_rate_mapping_currency


spec_symbol_rate_mapping, spec_symbol_rate_mapping_currency = get_symbol_rate_mapping(spec_symbol_rate_map)
spec_contract_symbol_rate_mapping, spec_contract_symbol_rate_mapping_currency = get_symbol_rate_mapping(spec_contract_symbol_rate_map)

RENAME_SPOT_CURRENCY = {'ZK': {'last_name': 'ZK',
                               'now_name': 'ZKJ',
                               'ts': '2024-06-20 11:00:00',
                               '备注': 'Websea 将支持Polyhedra Network（ZK)更名为Polyhedra Network（ZKJ),ZK将以1:1的比例更换为ZKJ。更名完成后，Polyhedra Network（ZK)将以新的代币符号ZKJ重新上线，2024年6月20日11:00（GMT+8)前强制停止。'
                                       '2024-06-24 22:00:00 上线ZKJ'
                               },
                        'JENNER': {'last_name': 'JENNER',
                                   'now_name': 'JENSOL',
                                   'ts': '2024-06-20 12:00:00',
                                   '备注': 'gateio 改名为 JENSOL，websea下线'
                                   },
                        }

if __name__ == '__main__':
    print('spot', f"{spec_symbol_rate_map=}")
    print('spot', f"{spec_symbol_rate_mapping=}")
    print('spot', f"{spec_symbol_rate_mapping_currency=}")
    print('contract', f"{spec_contract_symbol_rate_map=}")
    print('contract', f"{spec_contract_symbol_rate_mapping=}")
    print('contract', f"{spec_contract_symbol_rate_mapping_currency=}")
