#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询账户权益与持仓（现货钱包 + 未完成挂单）
参数全部写在脚本顶部，无 yaml。

用法：
  pip3 install requests
  python3 wbs_account_query.py
"""

from __future__ import annotations

import hashlib
import json
import random
import string
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================== 参数（按需修改） ========================
HOST = "https://oapi.websea.com"
TOKEN = "eb157511988afbb7771d34be9ay20973293"
SECRET_KEY = "dn3ptddjx8lav3472do1"

# 主交易对：用于估权益价、查挂单
SYMBOL = "WBS-USDT"

# 关注币种（为空则打印钱包里所有非零资产）
FOCUS_CURRENCIES = ["WBS", "USDT"]

# 是否查询未完成挂单
QUERY_OPEN_ORDERS = True

# 超时秒
TIMEOUT = 15
# =================================================================


class SpotApi:
    def __init__(self, host: str, token: str, secret_key: str, timeout: int = 15):
        self.host = host.rstrip("/")
        self.token = token
        self.secret_key = secret_key
        self.timeout = timeout
        self.session = requests.Session()

    def _sign(self, nonce: str, data: dict) -> str:
        tmp = [self.token, self.secret_key, nonce]
        for k, v in data.items():
            tmp.append("{}={}".format(k, v))
        return hashlib.sha1("".join(sorted(tmp)).encode("utf8")).hexdigest()

    def _headers(self, data: dict) -> dict:
        ran = "".join(random.sample(string.ascii_letters + string.digits, 5))
        nonce = "%d_%s" % (int(time.time() * 1000), ran)
        return {
            "Token": self.token,
            "Nonce": nonce,
            "Signature": self._sign(nonce, data),
            "User-Agent": "wbs_account_query/1.0",
        }

    def request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        data = dict(data or {})
        url = self.host + path
        headers = self._headers(data)
        method = method.upper()
        if method == "GET":
            r = self.session.get(
                url, params=data, headers=headers, timeout=self.timeout, verify=False
            )
        else:
            r = self.session.post(
                url, data=data, headers=headers, timeout=self.timeout, verify=False
            )
        try:
            body = r.json()
        except Exception:
            r.raise_for_status()
            raise RuntimeError("非 JSON 响应: {} {}".format(r.status_code, r.text[:200]))
        if r.status_code == 404 and isinstance(body, dict) and "errno" not in body:
            return {"errno": 404, "errmsg": "http 404", "result": body}
        if r.status_code >= 400 and not isinstance(body, dict):
            r.raise_for_status()
        return body

    def wallet_list(self, currency: str = "", show_all: bool = False) -> dict:
        data: Dict[str, Any] = {}
        if currency:
            data["currency"] = currency
        elif show_all:
            data["show_all"] = 1
        res = self.request("GET", "/v1/wallet/list", data)
        if res.get("errno") == 404:
            res = self.request("GET", "/openApi/wallet/list", data)
        return res

    def depth(self, symbol: str) -> dict:
        res = self.request("GET", "/openApi/market/depth", {"symbol": symbol})
        if res.get("errno") == 404:
            res = self.request("GET", "/v1/spot/market/depth", {"symbol": symbol})
        return res

    def open_orders(self, symbol: str) -> dict:
        res = self.request(
            "GET", "/v1/spot/orders/open", {"symbol": symbol, "limit": 100}
        )
        if res.get("errno") == 404:
            res = self.request(
                "GET", "/openApi/entrust/currentList", {"symbol": symbol}
            )
        return res


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def mid_from_depth(depth_result: dict) -> Optional[float]:
    bids = depth_result.get("bids") or []
    asks = depth_result.get("asks") or []
    if not bids or not asks:
        return None
    bid1 = fnum(bids[0][0])
    ask1 = fnum(asks[0][0])
    if bid1 <= 0 or ask1 <= 0:
        return None
    return (bid1 + ask1) / 2.0


def parse_wallet_rows(res: dict) -> List[dict]:
    if res.get("errno") != 0:
        raise RuntimeError("wallet 失败: {}".format(json.dumps(res, ensure_ascii=False)))
    result = res.get("result") or []
    if isinstance(result, dict):
        result = result.get("list") or result.get("data") or []
    rows = []
    for item in result if isinstance(result, list) else []:
        if not isinstance(item, dict):
            continue
        ccy = str(item.get("currency") or item.get("asset") or "")
        avail = fnum(item.get("available"))
        frozen = fnum(item.get("frozen") or item.get("hold") or 0)
        total = avail + frozen
        if not ccy:
            continue
        rows.append(
            {
                "currency": ccy,
                "available": avail,
                "frozen": frozen,
                "total": total,
            }
        )
    return rows


def parse_open_orders(res: dict) -> List[dict]:
    if res.get("errno") != 0:
        # 无挂单或接口异常时返回空，由调用方打印 raw
        return []
    result = res.get("result") or []
    if isinstance(result, dict):
        result = result.get("list") or result.get("orders") or result.get("data") or []
    out = []
    for item in result if isinstance(result, list) else []:
        if isinstance(item, dict):
            out.append(item)
    return out


def estimate_usdt(
    rows: List[dict], prices: Dict[str, float]
) -> Tuple[float, List[dict]]:
    """用 prices[currency]=USDT 价估算权益；USDT 按 1。"""
    detail = []
    equity = 0.0
    for r in rows:
        ccy = r["currency"]
        total = r["total"]
        if ccy.upper() in ("USDT", "USD"):
            px = 1.0
        else:
            px = prices.get(ccy)
        usdt = total * px if px is not None else None
        if usdt is not None:
            equity += usdt
        detail.append({**r, "price_usdt": px, "equity_usdt": usdt})
    return equity, detail


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> int:
    api = SpotApi(HOST, TOKEN, SECRET_KEY, TIMEOUT)
    print("[CFG] host={} symbol={}".format(HOST, SYMBOL))

    # ---- 资产 ----
    print_section("钱包资产")
    wallet_res = api.wallet_list(show_all=False)
    # print("[RAW] wallet {}".format(json.dumps(wallet_res, ensure_ascii=False)))
    rows = parse_wallet_rows(wallet_res)
    if FOCUS_CURRENCIES:
        focus = {c.upper() for c in FOCUS_CURRENCIES}
        rows = [r for r in rows if r["currency"].upper() in focus] or rows

    # 价格：主交易对中间价
    prices: Dict[str, float] = {"USDT": 1.0}
    base, quote = SYMBOL.split("-", 1) if "-" in SYMBOL else (SYMBOL, "USDT")
    depth_res = api.depth(SYMBOL)
    # print("[RAW] depth {}".format(json.dumps(depth_res, ensure_ascii=False)[:800]))
    if depth_res.get("errno") == 0:
        mid = mid_from_depth(depth_res.get("result") or {})
        if mid:
            prices[base] = mid
            print("[PRICE] {} mid={}".format(SYMBOL, mid))
        else:
            print("[PRICE] {} 盘口为空，无法估非稳定币权益".format(SYMBOL))
    else:
        print("[PRICE] depth 失败: {}".format(depth_res))

    equity, detail = estimate_usdt(rows, prices)
    print("\n{:<10} {:>16} {:>16} {:>16} {:>14} {:>16}".format(
        "币种", "可用", "冻结", "合计", "单价(U)", "权益(U)"
    ))
    print("-" * 96)
    for d in sorted(detail, key=lambda x: x["currency"]):
        px = d["price_usdt"]
        eu = d["equity_usdt"]
        print(
            "{:<10} {:>16.8f} {:>16.8f} {:>16.8f} {:>14} {:>16}".format(
                d["currency"],
                d["available"],
                d["frozen"],
                d["total"],
                ("{:.8f}".format(px) if px is not None else "-"),
                ("{:.4f}".format(eu) if eu is not None else "-"),
            )
        )
    print("-" * 96)
    print("估算现货权益合计(USDT): {:.4f}".format(equity))

    # ---- 挂单持仓 ----
    if QUERY_OPEN_ORDERS:
        print_section("未完成挂单 ({})".format(SYMBOL))
        oo_res = api.open_orders(SYMBOL)
        # print("[RAW] open_orders {}".format(json.dumps(oo_res, ensure_ascii=False)))
        orders = parse_open_orders(oo_res)
        if not orders:
            print("(无未完成挂单或解析为空)")
        else:
            buy_n = sell_n = 0.0
            buy_usdt = sell_usdt = 0.0
            print(
                "\n{:<22} {:<12} {:>14} {:>14} {:>14}".format(
                    "order_sn", "side/type", "price", "amount", "usdt~"
                )
            )
            print("-" * 80)
            for o in orders:
                sn = str(o.get("order_sn") or o.get("id") or "")
                side = str(o.get("side") or o.get("type") or "")
                price = fnum(o.get("price"))
                # 不同接口字段：number / amount / leftover
                amount = fnum(
                    o.get("number")
                    or o.get("amount")
                    or o.get("left_amount")
                    or o.get("surplus_amount")
                    or 0
                )
                usdt = price * amount if price and amount else 0.0
                side_l = side.lower()
                if "buy" in side_l or side_l in ("1", "b"):
                    buy_n += amount
                    buy_usdt += usdt
                elif "sell" in side_l or side_l in ("2", "s"):
                    sell_n += amount
                    sell_usdt += usdt
                print(
                    "{:<22} {:<12} {:>14} {:>14} {:>14.4f}".format(
                        sn[:22], side, price, amount, usdt
                    )
                )
            print("-" * 80)
            print(
                "挂单合计: 笔数={} 买量={} (~{:.4f}U) 卖量={} (~{:.4f}U)".format(
                    len(orders), buy_n, buy_usdt, sell_n, sell_usdt
                )
            )

    print_section("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
