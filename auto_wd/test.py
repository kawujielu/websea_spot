# -*- coding: utf-8 -*-
"""指定账号资金划转：open/get?url=quantuser/transfer"""
import hashlib
import random
import string
import time

import requests

# ========== 参数（按需改） ==========
BASE = "https://riskapi.websea.work/api/open/get"
TOKEN = "c1cf4185b2bed317aeb6e6674491fbef"  # 正式 risk token
SECRET = ""  # 无 secret 时留空
FROM_UID = 17
TO_UID = 196
CURRENCY = "GRAM"
AMOUNT = "33000"
NOTE = "转账备注"
# ==================================

params = {
    "url": "quantuser/transfer",
    "token": TOKEN,
    "from": FROM_UID,
    "to": TO_UID,
    "currency": CURRENCY,
    "amount": AMOUNT,
    "note": NOTE,
}
nonce = f"{int(time.time() * 1000)}_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
tmp = [TOKEN, SECRET, nonce] + [f"{k}={v}" for k, v in params.items()]
headers = {
    "Token": TOKEN,
    "Nonce": nonce,
    "Signature": hashlib.sha1("".join(sorted(tmp)).encode()).hexdigest(),
}

r = requests.get(BASE, params=params, headers=headers, timeout=30)
print("HTTP", r.status_code)
print(r.text)
j = r.json()
if j.get("errno") == 0:
    data = (j.get("result") or {}).get("data") or {}
    print("划转成功")
    print("转出余额:", data.get("from_balance"))
    print("转入余额:", data.get("to_balance"))
else:
    print("划转失败:", j.get("errno"), j.get("errmsg"))

