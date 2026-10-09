"""Binance 提币到 Websea 充值地址 + 现货余额查询。
提币: POST /sapi/v1/capital/withdraw/apply
余额: GET /api/v3/account
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests

# ========== 参数 ==========
API_KEY = "0k541tChzgmqgN6xPk3CwusnBSGEl0zLf0m45JbZ0Zb2j25vzHpJ1UFqXXcmM69L"
API_SECRET = "kOHonUaioVLjsKMGYOLBf1SxnNYu2VoaJdaZBzIQNC79EQg7x65xgvza9hgeEK34"
BASE_URL = "https://api.binance.com"

COIN = "USDT"
NETWORK = "TRX"  # Websea USDT 常用 TRC20；须与充值页网络一致
# Websea 196 账户 USDT-TRC20 充值地址
ADDRESS = "TANtNP8Dpeq8qNi6JkEwpRmUjBgMBpVt3x"
AMOUNT = "1000"
EXECUTE = True  # True 才真正提币
QUERY_BALANCE = True
# ==========================


def _signed_request(method, path, params=None):
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    query = urlencode(params)
    params["signature"] = hmac.new(
        API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}{path}"
    print("请求:", method, url, {k: v for k, v in params.items() if k != "signature"})
    r = requests.request(method, url, params=params, headers=headers, timeout=30)
    print("HTTP:", r.status_code)
    print("回报:", r.text)
    return r.json() if r.text else None


def get_spot_balances(asset=None):
    """查询现货账户余额。asset 为空则打印所有非零余额。"""
    data = _signed_request("GET", "/api/v3/account")
    if not data or "balances" not in data:
        return data
    rows = data["balances"]
    if asset:
        rows = [b for b in rows if b.get("asset") == asset]
    else:
        rows = [
            b for b in rows
            if float(b.get("free", 0) or 0) > 0 or float(b.get("locked", 0) or 0) > 0
        ]
    print("现货余额:")
    for b in rows:
        print(f"  {b.get('asset')}: free={b.get('free')} locked={b.get('locked')}")
    return rows


def withdraw(coin, address, amount, network=None):
    params = {
        "coin": coin,
        "address": address,
        "amount": amount,
    }
    if network:
        params["network"] = network
    return _signed_request("POST", "/sapi/v1/capital/withdraw/apply", params)


def main():
    if QUERY_BALANCE:
        get_spot_balances(COIN)
    print(f"BN提币 -> Websea  {COIN} amount={AMOUNT} network={NETWORK} address={ADDRESS}")
    if not EXECUTE:
        print("EXECUTE=False，未实际提币。确认后改 EXECUTE=True 再跑。")
        return
    withdraw(COIN, ADDRESS, AMOUNT, NETWORK)


if __name__ == "__main__":
    main()

