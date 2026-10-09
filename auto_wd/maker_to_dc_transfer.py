"""
做市账户 -> 17(spot_bak_4) -> 196(dc) 内部划转

部署: /home/ubuntu/code/spot_paddington/auto_wd/maker_to_dc_transfer.py
运行:
    cd /home/ubuntu/code/spot_paddington/auto_wd
    /home/ubuntu/miniconda3/envs/spot_paddington/bin/python3.11 maker_to_dc_transfer.py

余额查询: GET /openApi/wallet/list（同 select_spot_wallet.py）
划转接口: risk 后台 transfer/index（同 monitor）
"""

import hashlib
import random
import string
import time

import requests
import urllib3
from loguru import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- 划转参数（运行前修改） ----------
COIN = "USDT"
SZ = 100.0

# ---------- API ----------
SPOT_HOST = "https://oapi.websea.com"
RISK_HOST = "https://riskapi.websea.work/api/"
RISK_TOKEN = "c1cf4185b2bed317aeb6e6674491fbef"
REQUEST_TIMEOUT = 30
REMARK = "auto maker->17->196"

ERRNO_INSUFFICIENT = 20540
RETRY_SCALE = 0.999

# ---------- 账户（abclibs/account.py） ----------
ACCOUNTS = {
    "maker_near": {"token": "18c4725b9d218777c3863f812e21d9a2522", "sk": "2ijh2r7nf8nvjce4rnq7", "uid": 11},
    "maker_defense": {"token": "291d6fa8dc35f58690c38f7c3afcf2h2808", "sk": "7rk8zhyxbbxk5ro8r4to", "uid": 12},
    "maker_depth": {"token": "e5451dae5de519289e45aaab4be461f2856", "sk": "lmtn1yxnlwq6ecjqs5yv", "uid": 13},
    "spot_bak_4": {"token": "2ec49187f681419d1959af499d7bb0p3584", "sk": "wcj34ct96l2vh3s1hog7", "uid": 17},
    "dc": {"token": "78fc47c5590f77ca42d1e2c3bb432813", "sk": "5e5yg7ga285hctuqrtpb", "uid": 196},
}
MAKER_NAMES = ["maker_near", "maker_defense", "maker_depth"]
HUB_UID = ACCOUNTS["spot_bak_4"]["uid"]
DC_UID = ACCOUNTS["dc"]["uid"]

_currency_id_cache = {}


def _sign(token, sk, nonce, data):
    parts = [token, sk, nonce] + [f"{k}={v}" for k, v in data.items()]
    return hashlib.sha1("".join(sorted(parts)).encode("utf-8")).hexdigest()


def _spot_headers(token, sk, data):
    nonce = "%d_%s" % (int(time.time() * 1000), "".join(random.sample(string.ascii_letters + string.digits, 5)))
    return {"Token": token, "Nonce": nonce, "Signature": _sign(token, sk, nonce, data)}


def fetch_spot_wallet(token, sk):
    """openApi/wallet/list，逻辑同 select_spot_wallet.py"""
    params = {"show_all": 1}
    url = SPOT_HOST.rstrip("/") + "/openApi/wallet/list"
    resp = requests.get(
        url, params=params, headers=_spot_headers(token, sk, params),
        timeout=REQUEST_TIMEOUT, verify=False,
    )
    if resp.status_code != 200:
        return {"errno": -1, "errmsg": f"HTTP {resp.status_code}", "result": resp.text}
    return resp.json()


def coin_available(token, sk, coin):
    """某币种可用余额（available）"""
    payload = fetch_spot_wallet(token, sk)
    if payload.get("errno") != 0:
        logger.warning(f"查询钱包失败: {payload}")
        return 0.0
    for item in payload.get("result") or []:
        if str(item.get("currency", "")).upper() == coin.upper():
            return float(item.get("available") or 0)
    return 0.0


def _risk_get(path, params):
    url = RISK_HOST + path
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, verify=False)
    if resp.status_code != 200:
        return {"errno": -1, "errmsg": f"HTTP {resp.status_code}", "result": resp.text}
    return resp.json()


def currency_id(coin):
    if coin not in _currency_id_cache:
        res = _risk_get("currency/list", {"token": RISK_TOKEN, "name": coin})
        if res.get("errno") != 0 or not res.get("result"):
            raise RuntimeError(f"查询币种 ID 失败 {coin}: {res}")
        _currency_id_cache[coin] = res["result"][0]["id"]
    return _currency_id_cache[coin]


def transfer_spot(from_uid, to_uid, coin, amount):
    return _risk_get("transfer/index", {
        "token": RISK_TOKEN,
        "from_status": 1, "to_status": 1,
        "from_user_id": from_uid, "to_user_id": to_uid,
        "currency_id": currency_id(coin),
        "amount": amount, "remark": REMARK,
    })


def find_maker_with_balance(coin, sz):
    for name in MAKER_NAMES:
        meta = ACCOUNTS[name]
        bal = coin_available(meta["token"], meta["sk"], coin)
        logger.info(f"做市账户 {name} uid={meta['uid']} {coin} available={bal} 需要>{sz}")
        if bal > sz:
            return meta["uid"], bal
    return None, 0.0


def transfer_once(from_uid, to_uid, coin, amount):
    res = transfer_spot(from_uid, to_uid, coin, amount)
    if res.get("errno") == 0:
        logger.info(f"划转成功 {from_uid}->{to_uid} {coin} {amount} {res}")
        return True, amount
    logger.error(f"划转失败 {from_uid}->{to_uid} {coin} {amount} {res}，请人工处理")
    return False, None


def transfer_with_retry(from_uid, to_uid, coin, amount):
    try_amount = amount
    for attempt in (1, 2):
        res = transfer_spot(from_uid, to_uid, coin, try_amount)
        if res.get("errno") == 0:
            logger.info(f"划转成功 {from_uid}->{to_uid} {coin} {try_amount} {res}")
            return True, try_amount
        if res.get("errno") == ERRNO_INSUFFICIENT and attempt == 1:
            try_amount = amount * RETRY_SCALE
            logger.warning(f"余额不足，缩减为 {try_amount} 重试")
            continue
        logger.error(f"划转失败 {from_uid}->{to_uid} {coin} {try_amount} {res}，请人工处理")
        return False, None
    return False, None


def run(coin, sz):
    logger.info(f"开始划转 {coin=} {sz=}")

    from_uid, from_bal = find_maker_with_balance(coin, sz)
    if from_uid is None:
        logger.warning(f"账户 11/12/13 均无足够 {coin}（available > {sz}），跳过")
        return

    logger.info(f"选用 uid={from_uid} available={from_bal}")

    ok, actual = transfer_with_retry(from_uid, HUB_UID, coin, sz)
    if not ok:
        return

    ok, _ = transfer_once(HUB_UID, DC_UID, coin, actual)
    if not ok:
        logger.error(f"第二阶段 {HUB_UID}->{DC_UID} 失败，{coin}≈{actual} 可能滞留 uid={HUB_UID}，请人工处理")
        return

    logger.info(f"完成 {from_uid}->{HUB_UID}->{DC_UID} {coin} amount={actual}")


if __name__ == "__main__":
    run(COIN, SZ)
