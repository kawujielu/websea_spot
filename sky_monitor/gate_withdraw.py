# -*- coding: utf-8 -*-
"""Gate 现货余额提回 Websea 196 充值地址（独立脚本）。

接口（Gate API v4）:
  GET  /api/v4/spot/accounts     — 查现货可用余额
  GET  /api/v4/wallet/currency_chains?currency=XX — 可选，核对链名
  POST /api/v4/withdrawals       — 提币（需 API Key 开启「提现」权限）

文档: https://www.gate.com/docs/developers/apiv4/zh_CN/

用法:
  # 仅预览（默认不真正提币）
  python gate_to_196_withdraw.py
  python gate_to_196_withdraw.py --coin USDT
  python gate_to_196_withdraw.py --coin USDT --amount 50

  # 真正提币（需把 EXECUTE 改 True，或加 --execute）
  python gate_to_196_withdraw.py --execute
  python gate_to_196_withdraw.py --coin ETH --amount 0.01 --execute

规则（与 bn_hedge_to_196_withdraw.py 类似）:
  1) 默认扫现货 available > 0 的币种（可用 --coin 限定）
  2) 数量 = available - KEEP_THRESHOLDS 保留值；--amount 则按指定数量
  3) 196 地址取自 bn_hedge_to_196_withdraw.py 的 ADDR_196
  4) Gate chain 名用 CHAIN_TO_GATE 映射（TRC20→TRX, ERC20→ETH, BEP20→BSC ...）

依赖: pip install requests
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

BJT = ZoneInfo("Asia/Shanghai")

# ========================= 配置 =========================
GATE_HOST = "https://api.gateio.ws"
GATE_PREFIX = "/api/v4"

GATE_ACCOUNT = {
    "apiKey": "dd0eeebf5f147b1c8c1cfb5c1db2f38f",
    "secret": "a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e",
    "comment": "gate对冲",
}

EXECUTE = True  # True 或命令行 --execute 才真正提币
REQUEST_TIMEOUT = 30

# 提币后至少保留（与 BN 脚本同口径；未列出的币种保留 0）
KEEP_THRESHOLDS = {
    "BTC": 10,
    "ETH": 10,
    "SOL": 10,
    "BNB": 10,
    "TRX": 3000,
    "HOME": 100000,
}

# 196 充值地址（链 -> address / memo），来自 bn_hedge_to_196_withdraw.py
ADDR_196 = {
    "TRC20": ("TANtNP8Dpeq8qNi6JkEwpRmUjBgMBpVt3x", None),
    "ERC20": ("0x4ccf8f9d11c5dfcfa49aa939c83aa08e1b2bf8f0", None),
    "BEP20": ("0x4ccf8f9d11c5dfcfa49aa939c83aa08e1b2bf8f0", None),
    "SOL": ("12NWbNVqhjGuMee3eHM3su8F51Qegyw1B9mr63kL4iCE", None),
    "XRP": ("rGBwy1WNqtbZ2PpdQmpfGjR1GJ2Vtcugw1", "3379321141"),
    "TON": ("EQCXv4EABD76lIiUxP7bFlNJBMA2Obxn4AzmPXOyp2PhPlWS", "3379321141"),
    "LTC": ("LQRce4RxHJLHEJfE3ES3LtD6M3CoT3Vn3Q", None),
    "Arbitrum": ("0x4ccf8f9d11c5dfcfa49aa939c83aa08e1b2bf8f0", None),
    "DOGE": ("DH8R32oN2X58eEAVSQBYEPuJgxGdVmm6FV", None),
    "SUI": ("0x2da3629a33d5bae47d4b8bd609184a67ab1ef82cfaeecc3aee5d036fb3097808", None),
    "BTC": ("31pzpLv63V7cxtj7KsSmU4Dkcmk1FHgEwf", None),
    "POL": ("0x4ccf8f9d11c5dfcfa49aa939c83aa08e1b2bf8f0", None),
}

# 业务链名 -> Gate API chain 字段（见 GET /wallet/currency_chains）
CHAIN_TO_GATE = {
    "TRC20": "TRX",
    "ERC20": "ETH",
    "BEP20": "BSC",
    "SOL": "SOL",
    "Solana": "SOL",
    "XRP": "XRP",
    "TON": "TON",
    "LTC": "LTC",
    "Arbitrum": "ARBEVM",
    "DOGE": "DOGE",
    "SUI": "SUI",
    "BTC": "BTC",
    "POL": "MATIC",
}

# 币种默认链（摘自 bn_hedge_to_196_withdraw.py）
COIN_CHAIN = {
    "USDT": "TRC20",
    "USDC": "ERC20",
    "BTC": "BTC",
    "ETH": "ERC20",
    "BNB": "BEP20",
    "SOL": "SOL",
    "TRX": "TRC20",
    "XRP": "XRP",
    "LTC": "LTC",
    "DOGE": "DOGE",
    "SUI": "SUI",
    "ARB": "Arbitrum",
    "POL": "POL",
    "HOME": "ERC20",
    "GRAM": "TON",
    "TON": "TON",
    "DOGS": "TON",
    "MASK": "ERC20", "GALA": "ERC20", "WLFI": "ERC20", "ETHFI": "ERC20",
    "PEPE": "ERC20", "WLD": "ERC20", "FLOKI": "ERC20", "AXS": "ERC20",
    "ENS": "ERC20", "LINK": "ERC20", "MANA": "ERC20", "SAND": "ERC20",
    "SHIB": "ERC20", "COMP": "ERC20", "SUSHI": "ERC20", "AAVE": "ERC20",
    "CRV": "ERC20", "ANKR": "ERC20", "CHZ": "ERC20", "QNT": "ERC20",
    "UNI": "ERC20", "GLM": "ERC20", "MEME": "ERC20", "FTT": "ERC20",
    "CAKE": "ERC20", "GRT": "ERC20", "LDO": "ERC20", "ONDO": "ERC20",
    "IMX": "ERC20", "LPT": "ERC20", "JASMY": "ERC20", "AEVO": "ERC20",
    "ENA": "ERC20", "ZRO": "ERC20", "MOVE": "ERC20", "HYPER": "ERC20",
    "KERNEL": "ERC20", "SXT": "ERC20", "NEWT": "ERC20", "SKY": "ERC20",
    "CFX": "BEP20", "ASTER": "BEP20", "NXPC": "BEP20", "EGLD": "BEP20",
    "NEAR": "BEP20", "INJ": "BEP20", "BMT": "BEP20", "ERA": "BEP20", "C": "BEP20",
    "PENGU": "SOL", "TRUMP": "SOL", "ORCA": "SOL", "PNUT": "SOL",
    "ACT": "SOL", "RENDER": "SOL", "JUP": "SOL", "W": "SOL", "JTO": "SOL",
}

AMOUNT_DECIMALS = {
    "USDT": 2, "USDC": 2, "BTC": 6, "ETH": 6, "BNB": 5, "SOL": 4,
    "TRX": 2, "XRP": 2, "LTC": 4, "DOGE": 1, "SUI": 4, "ARB": 4, "POL": 2,
    "HOME": 2,
}
DEFAULT_DECIMALS = 4

# 扫余额时默认跳过的计价币（可用 --include-usdt 打开）
SKIP_COINS_DEFAULT = {"USDT"}
# =======================================================


def _log(msg: str) -> None:
    print("{} {}".format(datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def _fmt_amount(amount: float, decimals: int) -> Optional[str]:
    if amount <= 0:
        return None
    scale = 10 ** decimals
    truncated = math.floor(amount * scale + 1e-12) / scale
    if truncated <= 0:
        return None
    fmt = "{:." + str(decimals) + "f}"
    s = fmt.format(truncated)
    return s.rstrip("0").rstrip(".") if decimals > 0 else str(int(truncated))


def _coin_withdraw_cfg(coin: str) -> Optional[Tuple[str, str, Optional[str], str]]:
    """返回 (gate_chain, address, memo, biz_chain)。"""
    coin = str(coin).upper()
    biz_chain = COIN_CHAIN.get(coin)
    if not biz_chain:
        return None
    gate_chain = CHAIN_TO_GATE.get(biz_chain)
    addr_memo = ADDR_196.get(biz_chain)
    if not gate_chain or not addr_memo:
        return None
    address, memo = addr_memo
    return gate_chain, address, memo, biz_chain


# ---------- Gate 签名 / 请求 ----------
def _gate_sign(
    secret: str,
    method: str,
    url_path: str,
    timestamp: str,
    query_string: str = "",
    payload_string: str = "",
) -> str:
    hashed_payload = hashlib.sha512((payload_string or "").encode("utf-8")).hexdigest()
    sign_string = "{}\n{}\n{}\n{}\n{}".format(
        method, url_path, query_string or "", hashed_payload, timestamp
    )
    return hmac.new(
        secret.encode("utf-8"), sign_string.encode("utf-8"), hashlib.sha512
    ).hexdigest()


def gate_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
) -> Tuple[int, Any]:
    """
    path 例: /spot/accounts 或 /withdrawals（不含 host，含或不含 /api/v4 前缀均可）。
    """
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith(GATE_PREFIX):
        full_path = path
    else:
        full_path = GATE_PREFIX + path

    params = dict(params or {})
    query = "&".join("{}={}".format(k, params[k]) for k in params) if params else ""
    body_str = json.dumps(body) if body is not None else ""
    # POST 签名用空 query；GET 用 query
    sign_query = "" if method.upper() == "POST" else query
    sign_body = body_str if method.upper() == "POST" else ""

    ts = str(time.time())
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": GATE_ACCOUNT["apiKey"],
        "Timestamp": ts,
        "SIGN": _gate_sign(
            GATE_ACCOUNT["secret"], method.upper(), full_path, ts, sign_query, sign_body
        ),
    }
    url = GATE_HOST.rstrip("/") + full_path
    if method.upper() == "GET":
        if query:
            url = url + "?" + query
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    elif method.upper() == "POST":
        r = requests.post(url, data=body_str, headers=headers, timeout=REQUEST_TIMEOUT)
    else:
        raise ValueError("unsupported method {}".format(method))

    try:
        data = r.json() if r.text else None
    except ValueError:
        data = {"raw": r.text}
    if r.status_code >= 400:
        _log("Gate HTTP {} {} {} -> {}".format(r.status_code, method, full_path, data))
    return r.status_code, data


def gate_spot_available() -> Dict[str, float]:
    """GET /spot/accounts -> {CURRENCY: available}"""
    status, body = gate_request("GET", "/spot/accounts")
    if status != 200 or not isinstance(body, list):
        _log("查余额失败 status={} body={}".format(status, body))
        return {}
    out: Dict[str, float] = {}
    for row in body:
        coin = str(row.get("currency") or "").upper()
        avail = float(row.get("available") or 0)
        if coin and avail > 0:
            out[coin] = avail
    return out


def gate_withdraw(
    currency: str,
    amount: float,
    chain: str,
    address: str,
    memo: Optional[str] = None,
    execute: bool = False,
) -> Any:
    """POST /withdrawals"""
    decimals = AMOUNT_DECIMALS.get(currency.upper(), DEFAULT_DECIMALS)
    amt_s = _fmt_amount(amount, decimals)
    if not amt_s:
        _log("提币数量过小跳过 currency={} amount={}".format(currency, amount))
        return None
    payload: Dict[str, Any] = {
        "currency": currency.upper(),
        "amount": amt_s,
        "address": address,
        "chain": chain,
    }
    if memo:
        payload["memo"] = str(memo)

    _log(
        "提币请求 currency={} amount={} chain={} address={} memo={} EXECUTE={}".format(
            currency, amt_s, chain, address, memo, execute
        )
    )
    if not execute:
        return {"dry_run": True, "payload": payload}

    status, body = gate_request("POST", "/withdrawals", body=payload)
    return {"http_status": status, "body": body}


def plan_amount(coin: str, available: float, amount_arg: Optional[float]) -> Optional[float]:
    if amount_arg is not None:
        if amount_arg <= 0:
            return None
        if amount_arg > available + 1e-12:
            _log(
                "指定数量超过可用 coin={} amount={} available={}".format(
                    coin, amount_arg, available
                )
            )
            return None
        return float(amount_arg)
    keep = float(KEEP_THRESHOLDS.get(coin, 0) or 0)
    send = available - keep
    if send <= 0:
        _log("保留阈值跳过 coin={} available={} keep={}".format(coin, available, keep))
        return None
    return send


def run_withdraw(
    coins: Optional[List[str]],
    amount: Optional[float],
    execute: bool,
    include_usdt: bool,
) -> int:
    bals = gate_spot_available()
    _log("Gate非零available: {}".format(dict(sorted(bals.items()))))
    if not bals:
        _log("无可用余额，退出")
        return 1

    if coins:
        targets = [c.upper() for c in coins]
    else:
        targets = sorted(bals.keys())
        if not include_usdt:
            targets = [c for c in targets if c not in SKIP_COINS_DEFAULT]

    single_coin = bool(coins and len(coins) == 1)
    if amount is not None and not single_coin:
        _log("提示: --amount 仅在指定单个 --coin 时生效；本次按 available-保留阈值 计算")

    ok = 0
    fail = 0
    skip = 0
    for coin in targets:
        avail = float(bals.get(coin) or 0)
        if avail <= 0:
            _log("无余额跳过 coin={}".format(coin))
            skip += 1
            continue
        send = plan_amount(coin, avail, amount if single_coin else None)
        if send is None:
            skip += 1
            continue

        cfg = _coin_withdraw_cfg(coin)
        if not cfg:
            _log("无196提币配置跳过 coin={} available={} send={}".format(coin, avail, send))
            skip += 1
            continue
        gate_chain, address, memo, biz_chain = cfg
        keep = float(KEEP_THRESHOLDS.get(coin, 0) or 0)
        res = gate_withdraw(coin, send, gate_chain, address, memo, execute=execute)
        _log(
            "提币结果 coin={} send={} keep={} biz_chain={} gate_chain={} res={}".format(
                coin, send, keep, biz_chain, gate_chain, res
            )
        )
        if not execute:
            ok += 1
            continue
        if isinstance(res, dict) and res.get("http_status") in (200, 201):
            ok += 1
        else:
            fail += 1
        # Gate 提现限频约 1r/3s
        time.sleep(3.1)

    _log(
        "完成 EXECUTE={} ok={} fail={} skip={}".format(execute, ok, fail, skip)
    )
    return 0 if fail == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 提币到 Websea 196")
    parser.add_argument("--coin", "-c", action="append", help="币种，可多次；不传则扫全部非零")
    parser.add_argument("--amount", "-a", type=float, default=None, help="提币数量（仅单币时生效）")
    parser.add_argument("--execute", action="store_true", help="真正提币（默认干跑）")
    parser.add_argument("--include-usdt", action="store_true", help="扫全币时包含 USDT")
    args = parser.parse_args()

    execute = bool(EXECUTE or args.execute)
    _log(
        "启动 account={} EXECUTE={} coins={} amount={}".format(
            GATE_ACCOUNT.get("comment"), execute, args.coin, args.amount
        )
    )
    if not execute:
        _log("当前为干跑模式：只打印请求，不真实提币。确认后加 --execute 或改 EXECUTE=True")

    return run_withdraw(
        coins=args.coin,
        amount=args.amount,
        execute=execute,
        include_usdt=args.include_usdt,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        _log("已退出")
        raise SystemExit(0)

