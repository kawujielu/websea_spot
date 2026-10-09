# -*- coding: utf-8 -*-
"""从 Websea 196 账户提币到 Binance 充值地址。

用法:
  python 196_to_bn_withdraw.py USDT 1000
  python 196_to_bn_withdraw.py --coin ETH --amount 0.5
  python 196_to_bn_withdraw.py USDT 1000 --dry-run

地址口径对齐 wd.py 中路由到 bn 的币种（不含 Gate/Kraken）。
依赖: pip install requests
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import string
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 默认参数（也可用命令行覆盖） ==========
COIN = "USDT"
AMOUNT = 100.0
EXECUTE = True  # False / --dry-run 只打印不真正提币
# ========== 196 账户 ==========
TOKEN = "78fc47c5590f77ca42d1e2c3bb432813"
SECRET_KEY = "5e5yg7ga285hctuqrtpb"
SPOT_HOST = "https://oapi.websea.work"  # 提币接口同 abc_api
WALLET_HOST = "https://oapi.websea.com"  # 余额查询同 wd.py
# 币种 -> (chain, address[, memo])，对齐 wd.py → bn
BN_ADDRS = {
    "USDT": ("TRC20", "TLxBj9Edy11Wps3Yf7oufEeVcb8R4hyjPt"),
    "BTC": ("BTC", "12yDuBueTUZcDw9P7VNdnYbd4Q9GQLuoiN"),
    "ETH": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SOL": ("Solana", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "BNB": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "TRX": ("TRC20", "TLxBj9Edy11Wps3Yf7oufEeVcb8R4hyjPt"),
    "XRP": ("XRP", "rNxp4h8apvRis6mJf9Sh8C6iRxfrDWN7AV", "493586538"),
    "MASK": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "GALA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "WLFI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ETHFI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "PEPE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "WLD": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "LTC": ("LTC", "LNu4gJwxujrvxhDuWcT7YDhvCWCyWgovVp"),
    "CFX": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "FLOKI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ASTER": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "NXPC": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "USDC": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "DOGE": ("DOGE", "DRu9tqGhqvZRqzGg7nzTpsvKuzBSiWWHUR"),
    "AXS": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ENS": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "LINK": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "MANA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SAND": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SHIB": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "COMP": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SUSHI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "AAVE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "CRV": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ANKR": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "CHZ": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "QNT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "UNI": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "GLM": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "MEME": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "FTT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "CAKE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "GRT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "LDO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ONDO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "IMX": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "LPT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "JASMY": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "AEVO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ENA": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ZRO": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "POL": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "MOVE": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "HYPER": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "KERNEL": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SXT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "NEWT": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "SKY": ("ERC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "EGLD": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "NEAR": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "INJ": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "BMT": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ERA": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "C": ("BEP20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "ORDI": ("BRC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "BEAMX": ("BRC20", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "PENGU": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "TRUMP": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "ORCA": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "PNUT": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "ACT": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "RENDER": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "JUP": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "W": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "JTO": ("SOL", "4EqYYBZQc1uVHGuekdXtrWE7j72ZYNoQjFEsWr5h4Ctf"),
    "TIA": ("Celestia", "celestia1fd3mclxp4e2fh0wpau3eg55x2fsm7yjxzg29j2", "106324248"),
    "SUI": ("SUI", "0x2555c3903f45c653a193d241c48aa67de38032e7835ff4648c262ee1fe99f174"),
    "ARB": ("Arbitrum", "0xb46a8d516fb7e6c12c34654e635558678a2f589b"),
    "DOGS": ("TON", "UQB0dW0k-KBfbI1qMhav9iqKuBsRhvZQPGHkZZvVsiUnQowh"),
    "GRAM": ("TON", "UQB0dW0k-KBfbI1qMhav9iqKuBsRhvZQPGHkZZvVsiUnQowh"),
}
DEFAULT_DECIMALS = 4
# ============================================


def _fmt_amount(amount: float, decimals: int = DEFAULT_DECIMALS) -> str | None:
    decimals = max(0, int(decimals))
    scale = 10 ** decimals
    floored = math.floor(float(amount) * scale + 1e-12) / scale
    if floored <= 0:
        return None
    if decimals == 0:
        return str(int(floored))
    s = f"{floored:.{decimals}f}".rstrip("0").rstrip(".")
    return s or None


def _headers(data: dict) -> dict:
    nonce = "%d_%s" % (
        int(time.time() * 1000),
        "".join(random.sample(string.ascii_letters + string.digits, 5)),
    )
    parts = [TOKEN, SECRET_KEY, nonce] + [f"{k}={v}" for k, v in data.items()]
    return {
        "Token": TOKEN,
        "Nonce": nonce,
        "Signature": hashlib.sha1("".join(sorted(parts)).encode("utf-8")).hexdigest(),
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        ),
    }


def available(coin: str) -> float:
    params = {"show_all": 1}
    resp = requests.get(
        f"{WALLET_HOST.rstrip('/')}/openApi/wallet/list",
        params=params,
        headers=_headers(params),
        timeout=30,
        verify=False,
    )
    payload = resp.json()
    if payload.get("errno") != 0:
        raise RuntimeError(f"查余额失败: {payload}")
    for item in payload.get("result") or []:
        if str(item.get("currency", "")).upper() == coin.upper():
            return float(item.get("available") or 0)
    return 0.0


def withdraw(coin: str, amount: float, *, execute: bool = True) -> dict:
    coin = coin.upper()
    cfg = BN_ADDRS.get(coin)
    if not cfg:
        raise ValueError(f"无 BN 提币地址配置: {coin}，请在 BN_ADDRS 中补充")
    chain, address = cfg[0], cfg[1]
    memo = cfg[2] if len(cfg) > 2 else None
    amt_s = _fmt_amount(amount)
    if amt_s is None:
        raise ValueError(f"数量过小: {amount}")

    bal = available(coin)
    print(f"196 available {coin}={bal} need={amt_s} chain={chain} address={address}")
    if bal + 1e-12 < float(amt_s):
        raise RuntimeError(f"196 余额不足 {coin}: available={bal} need={amt_s}")

    data = {
        "address": address,
        "amount": amt_s,
        "currency": coin,
        "chain": chain,
    }
    if memo:
        data["memo"] = memo

    print(f"提币请求 {data} execute={execute}")
    if not execute:
        return {"dry_run": True, "data": data}

    resp = requests.post(
        f"{SPOT_HOST.rstrip('/')}/openApi/wallet/withdraw",
        data=data,
        headers=_headers(data),
        timeout=30,
        verify=False,
    )
    try:
        result = resp.json()
    except Exception:
        result = {"http": resp.status_code, "text": resp.text}
    print(f"提币结果: {result}")
    return result


def main():
    p = argparse.ArgumentParser(description="196 → Binance 提币")
    p.add_argument("coin", nargs="?", default=COIN, help="币种，如 USDT")
    p.add_argument("amount", nargs="?", type=float, default=AMOUNT, help="数量")
    p.add_argument("--coin", dest="coin_opt", help="币种（覆盖位置参数）")
    p.add_argument("--amount", dest="amount_opt", type=float, help="数量（覆盖位置参数）")
    p.add_argument("--dry-run", action="store_true", help="只校验/打印，不真正提币")
    args = p.parse_args()

    coin = (args.coin_opt or args.coin or COIN).upper()
    amount = float(args.amount_opt if args.amount_opt is not None else args.amount)
    execute = EXECUTE and not args.dry_run
    withdraw(coin, amount, execute=execute)


if __name__ == "__main__":
    main()
