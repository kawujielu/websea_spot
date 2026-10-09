import asyncio
import json
import traceback
import requests
from config.infor_load import account
from loguru import logger
from libs.database.getmysql import sync_mysql_connect
import pymysql

def contract_support_symbols():
    contract_symbols_url = "https://coapi.websea.com/openApi/contract/symbols"
    try:
        res = requests.get(contract_symbols_url, timeout=2, verify=False)
        if res.status_code == 200:
            res = json.loads(res.text).get("result")
            r = [r["symbol"] for r in res]
            return r
    except BaseException as e:
        msg = f"contract_support_symbols {traceback.format_exc()}"
        logger.error(msg)
    return []


sql = f"SELECT symbol from contract_mongodb_day"
res = sync_mysql_connect(sql)

SYMBOLS_CONTRACT_PAIR = contract_support_symbols()
HISTORY_SYMBOLS = list(set([r[0] for r in res]))

SYMBOLS_OFFLINE = list(set(HISTORY_SYMBOLS) - set(SYMBOLS_CONTRACT_PAIR))
logger.info(f"{SYMBOLS_CONTRACT_PAIR=} \n {SYMBOLS_OFFLINE=}")

SYMBOLS_LIST_PROJECT = []

SYMBOLS_CONTRACT_OUT = SYMBOLS_OFFLINE + SYMBOLS_LIST_PROJECT

# SYMBOLS_CONTRACT_PAIR = [f"{k}-{i}" for k, v in libs_config.CONTRACT_CURRENCY_CONFIG.items() for i in v['zone']]


SYMBOLS_CONTRACT_LIST = list(set([i.split('-')[0] for i in SYMBOLS_CONTRACT_PAIR] + [i.split('-')[1] for i in SYMBOLS_CONTRACT_PAIR]))
SYMBOLS_QUOTE = ['USDT']
SYMBOLS_CONTRACT_PAIR_DANGEROUS_LEVEL = {}

# 账户信息---------------------------------------------------------------------------------------------------------------------

contract_account = {k: {'apikey': {'token': v['token'], 'sk': v['sk']}, 'id': v['uid'], 'boundary_amount': 3, 'boundary_amount_coef': 0.7, 'boundary_frozen': 0.7, 'purpose': k}
                    for k, v in account.items() if k not in ['dc', 'xdc'] and v['token'] and v['sk'] and 'contract' in k}

acc_id_contract = [str(v['id']) for k, v in contract_account.items()]


