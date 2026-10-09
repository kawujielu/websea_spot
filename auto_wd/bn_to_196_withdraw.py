# -*- coding: utf-8 -*-
"""监控 hedge.orders：BN 对冲单成交后，按买卖方向提回 Websea 196。

规则：
  1) 启动时只记水位，不做提币；仅处理启动后新出现的订单
  2) 按 orderId 查 BN：FILLED，或 CANCELED/EXPIRED 且已成交量>0 → 触发
  3) BUY（用 USDT 买 coin）：累计本笔成交量到该币 pending
  4) SELL（把 coin 卖成 USDT）：
       - 若账户整体 USDT free < USDT_KEEP_THRESHOLD → 保留，不累计/不提
       - 若 >= 阈值 → 累计本次 cummulativeQuoteQty 到 USDT pending
  5) 每个币种：pending 折合 USDT >= MIN_WITHDRAW_USDT 才真正提币；实际提币 = min(pending, free)
  6) 无链/地址配置则跳过

  python bn_to_196_withdraw.py

依赖：mysql-connector-python、requests
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

BJT = ZoneInfo("Asia/Shanghai")

# ========================= 配置 =========================
API_KEY = "0k541tChzgmqgN6xPk3CwusnBSGEl0zLf0m45JbZ0Zb2j25vzHpJ1UFqXXcmM69L"
API_SECRET = "kOHonUaioVLjsKMGYOLBf1SxnNYu2VoaJdaZBzIQNC79EQg7x65xgvza9hgeEK34"
BASE_URL = "https://api.binance.com"

MYSQL_HOST = "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com"
MYSQL_USER = "admin"
MYSQL_PASSWORD = "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2"
MYSQL_DATABASE = "hedge"
MYSQL_PORT = 3306
TABLE_NAME = "orders"
EXCHANGE = "bn"

EXECUTE = True  # True 才真正提币
POLL_SEC = 10
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bn_hedge_to_196_state.json"
)

# SELL 后：整体 USDT 低于此阈值则保留，不低于则累计「本次」USDT
USDT_KEEP_THRESHOLD = 20000.0
# 每个币种累计未提金额折合 USDT 达到此值才提币
MIN_WITHDRAW_USDT = 1000.0

# 196 充值地址（链 -> address / memo）
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

CHAIN_TO_BN_NETWORK = {
    "TRC20": "TRX",
    "ERC20": "ETH",
    "BEP20": "BSC",
    "SOL": "SOL",
    "Solana": "SOL",
    "XRP": "XRP",
    "TON": "TON",
    "LTC": "LTC",
    "Arbitrum": "ARBITRUM",
    "DOGE": "DOGE",
    "SUI": "SUI",
    "BTC": "BTC",
    "POL": "MATIC",
}

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

TERMINAL_FULL = {"FILLED"}
TERMINAL_PARTIAL_CANCEL = {"CANCELED", "CANCELLED", "EXPIRED"}
# 各币种累计未提数量（持久化到 STATE_FILE.pending_amt）
_PENDING: Dict[str, float] = {}
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


def _coin_usdt_value(coin: str, amount: float) -> float:
    """未提数量折合 USDT；稳定币按 1:1，其它走 BN 现货价。"""
    c = str(coin).upper()
    amt = float(amount or 0)
    if amt <= 0:
        return 0.0
    if c in ("USDT", "USDC", "BUSD", "FDUSD"):
        return amt
    try:
        r = requests.get(
            "{}/api/v3/ticker/price".format(BASE_URL),
            params={"symbol": "{}USDT".format(c)},
            timeout=10,
        )
        px = float((r.json() or {}).get("price") or 0)
        return amt * px if px > 0 else 0.0
    except Exception as e:
        _log("估值失败 coin={} amount={} err={}".format(c, amt, e))
        return 0.0


def _mask_address(address: str) -> str:
    addr = str(address or "")
    if len(addr) <= 7:
        return addr + "*****" if addr else ""
    return addr[:7] + "*****"


def _send_tg(msg: str) -> None:
    """ser=spot_hedge（与 libs/senddd.py 一致）；不加载 senddd，避免 uvloop 依赖。"""
    try:
        # 与 senddd.tgtalk["spot_hedge"] 保持一致
        token = "5802332386:AAEIAje0gzR1lzrrlq489pSsP0z94YI7Xlw"
        chat_id = "-5287616263"
        url = "https://api.telegram.org/bot{}/sendMessage".format(token)
        r = requests.post(
            url, data={"chat_id": chat_id, "text": msg}, timeout=10
        )
        if r.status_code >= 400:
            _log("tg发送失败: http={} body={}".format(r.status_code, r.text))
    except Exception as e:
        _log("tg发送失败: {}".format(e))


def _fail_info(res: Any) -> str:
    if res is None:
        return "提币请求无返回"
    if not isinstance(res, dict):
        return str(res)
    parts = []
    if res.get("code") is not None:
        parts.append("code={}".format(res.get("code")))
    if res.get("msg"):
        parts.append(str(res.get("msg")))
    elif res.get("message"):
        parts.append(str(res.get("message")))
    if res.get("raw"):
        parts.append(str(res.get("raw")))
    if not parts:
        parts.append(str(res))
    return " | ".join(parts)


def _notify_bn_to_196(
    coin: str,
    amount_s: str,
    network: str,
    address: str,
    *,
    ok: bool,
    fail_detail: str = "",
) -> None:
    """发起 BN→196 提币后，成功/失败各只发一条 Telegram。"""
    title = "binance到196发起提币" if ok else "binance到196提币失败"
    lines = [
        title,
        "时间：{}".format(datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")),
        "币种：{}".format(str(coin).upper()),
        "数量：{}".format(amount_s),
        "链：{}".format(network),
        "目标地址：{}".format(_mask_address(address)),
    ]
    if not ok and fail_detail:
        lines.append("失败信息：{}".format(fail_detail))
    _send_tg("\n".join(lines))


def _coin_withdraw_cfg(coin: str) -> Optional[Tuple[str, str, Optional[str]]]:
    coin = str(coin).upper()
    chain = COIN_CHAIN.get(coin)
    if not chain:
        return None
    bn_net = CHAIN_TO_BN_NETWORK.get(chain)
    addr_memo = ADDR_196.get(chain)
    if not bn_net or not addr_memo:
        return None
    address, memo = addr_memo
    return bn_net, address, memo


def _base_quote_from_symbol(symbol: str) -> Tuple[str, str]:
    s = str(symbol or "").upper().replace("_", "-")
    if "-" in s:
        base, quote = s.split("-", 1)
        return base, quote
    if s.endswith("USDT"):
        return s[:-4], "USDT"
    if s.endswith("USDC"):
        return s[:-4], "USDC"
    return s, "USDT"


# ---------- BN API ----------
def _signed_request(method: str, path: str, params: Optional[dict] = None):
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000)
    query = urlencode(params)
    params["signature"] = hmac.new(
        API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}{path}"
    r = requests.request(method, url, params=params, headers=headers, timeout=30)
    try:
        body = r.json() if r.text else None
    except ValueError:
        body = {"raw": r.text}
    if r.status_code >= 400:
        _log("BN HTTP {} {} {} -> {}".format(r.status_code, method, path, body))
    return body


def bn_get_order(symbol: str, order_id: str) -> Optional[dict]:
    data = _signed_request(
        "GET",
        "/api/v3/order",
        {"symbol": str(symbol).replace("-", "").replace("_", ""), "orderId": order_id},
    )
    if not isinstance(data, dict) or "status" not in data:
        return None
    return data


def bn_all_free() -> Dict[str, float]:
    data = _signed_request("GET", "/api/v3/account")
    if not data or "balances" not in data:
        return {}
    out = {}
    for b in data["balances"]:
        free = float(b.get("free") or 0)
        if free > 0:
            out[str(b.get("asset", "")).upper()] = free
    return out


def bn_withdraw(coin: str, amount: float, network: str, address: str, address_tag: Optional[str] = None):
    decimals = AMOUNT_DECIMALS.get(coin.upper(), DEFAULT_DECIMALS)
    amt_s = _fmt_amount(amount, decimals)
    if not amt_s:
        _log("提币数量过小跳过 coin={} amount={}".format(coin, amount))
        return None
    params = {
        "coin": coin.upper(),
        "address": address,
        "amount": amt_s,
        "network": network,
    }
    if address_tag:
        params["addressTag"] = address_tag
    _log(
        "提币请求 coin={} amount={} network={} address={} tag={} EXECUTE={}".format(
            coin, amt_s, network, address, address_tag, EXECUTE
        )
    )
    if not EXECUTE:
        return {"dry_run": True, "params": params, "amount_s": amt_s}
    res = _signed_request("POST", "/sapi/v1/capital/withdraw/apply", params)
    if isinstance(res, dict):
        res = dict(res)
        res["amount_s"] = amt_s
    return res


def withdraw_coin(coin: str, amount: float) -> Any:
    """累计未提；折合 USDT >= MIN_WITHDRAW_USDT 才提 min(pending, free)。"""
    coin = str(coin).upper()
    _PENDING[coin] = float(_PENDING.get(coin, 0) or 0) + float(amount or 0)
    pending = float(_PENDING[coin])
    usdt_val = _coin_usdt_value(coin, pending)
    if usdt_val < MIN_WITHDRAW_USDT:
        _log(
            "未达提币阈值跳过 coin={} pending={} usdt≈{:.2f} < {}".format(
                coin, pending, usdt_val, MIN_WITHDRAW_USDT
            )
        )
        return None

    cfg = _coin_withdraw_cfg(coin)
    if not cfg:
        _log("无196提币配置跳过 coin={} pending={}".format(coin, pending))
        return None
    bals = bn_all_free()
    free = float(bals.get(coin, 0) or 0)
    send = min(pending, free)
    if send <= 0:
        _log("可用不足跳过 coin={} pending={} free={}".format(coin, pending, free))
        return None
    if send + 1e-12 < pending:
        _log(
            "pending大于可用，按可用截断 coin={} pending={} free={} send={}".format(
                coin, pending, free, send
            )
        )
    network, address, tag = cfg
    res = bn_withdraw(coin, send, network, address, tag)
    _log(
        "提币结果 coin={} pending={} send={} free={} usdt≈{:.2f} res={}".format(
            coin, pending, send, free, usdt_val, res
        )
    )
    # 真正发起提币后发一条 TG：成功/失败各只发一次（dry_run 不发）
    if EXECUTE and not (isinstance(res, dict) and res.get("dry_run")):
        amt_s = None
        if isinstance(res, dict):
            amt_s = res.get("amount_s")
        if not amt_s:
            amt_s = _fmt_amount(
                send, AMOUNT_DECIMALS.get(coin, DEFAULT_DECIMALS)
            ) or str(send)
        if isinstance(res, dict) and res.get("id"):
            _PENDING[coin] = max(0.0, pending - send)
            _notify_bn_to_196(coin, amt_s, network, address, ok=True)
        else:
            _notify_bn_to_196(
                coin,
                amt_s,
                network,
                address,
                ok=False,
                fail_detail=_fail_info(res),
            )
    elif isinstance(res, dict) and res.get("dry_run"):
        # dry_run 也扣减 pending，避免本地无限堆积
        _PENDING[coin] = max(0.0, pending - send)
    return res


def order_is_done(status: str, executed_qty: float) -> bool:
    st = str(status or "").upper()
    if st in TERMINAL_FULL:
        return True
    if st in TERMINAL_PARTIAL_CANCEL and executed_qty > 0:
        return True
    return False


# ---------- MySQL / 状态 ----------
def connect_mysql():
    import mysql.connector

    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT,
    )


def load_state() -> dict:
    global _PENDING
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"baseline_id": None, "processed_orders": [], "watching": {}}
    _PENDING = {
        str(k).upper(): float(v)
        for k, v in (data.get("pending_amt") or {}).items()
        if float(v or 0) > 0
    }
    return data


def save_state(state: dict) -> None:
    processed = state.get("processed_orders") or []
    state["processed_orders"] = processed[-5000:]
    state["pending_amt"] = {k: v for k, v in _PENDING.items() if v > 0}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_baseline_id(cursor) -> int:
    tbl = TABLE_NAME.replace("`", "")
    cursor.execute(
        "SELECT COALESCE(MAX(id), 0) FROM `{table}` WHERE exchange=%s".format(table=tbl),
        (EXCHANGE,),
    )
    return int(cursor.fetchone()[0] or 0)


def fetch_new_orders(cursor, after_id: int) -> List[dict]:
    tbl = TABLE_NAME.replace("`", "")
    sql = (
        "SELECT id, orderId, exchange, symbol, side, amount, fillsz, status, currency, price "
        "FROM `{table}` WHERE exchange=%s AND id > %s ORDER BY id ASC"
    ).format(table=tbl)
    cursor.execute(sql, (EXCHANGE, after_id))
    cols = [
        "id", "orderId", "exchange", "symbol", "side", "amount",
        "fillsz", "status", "currency", "price",
    ]
    out = []
    for row in cursor.fetchall() or []:
        d = dict(zip(cols, row))
        d["id"] = int(d["id"])
        d["orderId"] = str(d["orderId"] or "")
        d["symbol"] = str(d["symbol"] or "")
        d["side"] = str(d["side"] or "")
        d["status"] = str(d["status"] or "")
        d["currency"] = str(d.get("currency") or "")
        d["amount"] = float(d["amount"] or 0)
        d["fillsz"] = float(d["fillsz"] or 0)
        d["price"] = float(d.get("price") or 0)
        out.append(d)
    return out


def handle_filled_order(order: dict, bn: Optional[dict], executed: float) -> None:
    """按买卖方向提币。"""
    side = str((bn or {}).get("side") or order.get("side") or "").upper()
    symbol = order.get("symbol") or (bn or {}).get("symbol") or ""
    base, quote = _base_quote_from_symbol(symbol)
    if order.get("currency"):
        base = str(order["currency"]).upper()

    if side == "BUY":
        # 用 USDT 买 coin → 只提本笔成交量 executedQty，不是账户该币全部余额
        _log(
            "BUY成交提币(本笔成交量) orderId={} symbol={} base={} 本笔executedQty={}".format(
                order.get("orderId"), symbol, base, executed
            )
        )
        withdraw_coin(base, executed)
        return

    if side == "SELL":
        # 卖成 USDT → 看整体 USDT 是否超过保留阈值，是则提本次 quote 金额
        quote_got = 0.0
        if bn:
            quote_got = float(bn.get("cummulativeQuoteQty") or 0)
        if quote_got <= 0 and executed > 0:
            # 回退：库内无 quote，用 fillsz * price 估（尽量少用）
            px = float((bn or {}).get("price") or order.get("price") or 0)
            quote_got = executed * px if px > 0 else 0.0
        bals = bn_all_free()
        usdt_free = float(bals.get("USDT", 0) or 0)
        _log(
            "SELL成交 orderId={} symbol={} quote_got={} usdt_free={} threshold={}".format(
                order.get("orderId"), symbol, quote_got, usdt_free, USDT_KEEP_THRESHOLD
            )
        )
        if usdt_free < USDT_KEEP_THRESHOLD:
            _log(
                "USDT低于阈值保留，不提币 usdt_free={} < {}".format(
                    usdt_free, USDT_KEEP_THRESHOLD
                )
            )
            return
        if quote_got <= 0:
            _log("本次USDT成交额为0，跳过")
            return
        withdraw_coin("USDT", quote_got)
        return

    _log("未知side，不提币 orderId={} side={}".format(order.get("orderId"), side))


def check_and_maybe_withdraw(order: dict) -> bool:
    """
    查 BN 订单状态；终态有成交则按 BUY/SELL 提币。
    返回 True 表示该订单已终态处理完（含无成交撤单，不再盯）。
    """
    oid = order["orderId"]
    symbol = order["symbol"]
    bn = bn_get_order(symbol, oid)
    if bn:
        status = str(bn.get("status") or "")
        executed = float(bn.get("executedQty") or 0)
        _log(
            "BN订单 status orderId={} symbol={} side={} status={} executedQty={} "
            "cumQuote={} db_status={}".format(
                oid,
                symbol,
                bn.get("side"),
                status,
                executed,
                bn.get("cummulativeQuoteQty"),
                order.get("status"),
            )
        )
    else:
        status = order.get("status") or ""
        executed = float(order.get("fillsz") or 0)
        _log(
            "BN查询失败，用库状态 orderId={} status={} fillsz={}".format(
                oid, status, executed
            )
        )

    st = status.upper()
    if st in {"NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"}:
        return False

    if order_is_done(st, executed):
        _log("触发提币判断 orderId={} status={} executedQty={}".format(oid, status, executed))
        handle_filled_order(order, bn, executed)
        return True

    if st in TERMINAL_PARTIAL_CANCEL | {"REJECTED", "FAILED"} and executed <= 0:
        _log("无成交终态，不提币 orderId={} status={}".format(oid, status))
        return True

    return False


def main() -> int:
    state = load_state()
    db = connect_mysql()
    cursor = db.cursor()
    try:
        if state.get("baseline_id") is None:
            state["baseline_id"] = fetch_baseline_id(cursor)
            state["processed_orders"] = []
            state["watching"] = {}
            save_state(state)
            _log(
                "启动水位 baseline_id={}（此前订单不提币） EXECUTE={} USDT_KEEP={} MIN_WD_USDT={}".format(
                    state["baseline_id"], EXECUTE, USDT_KEEP_THRESHOLD, MIN_WITHDRAW_USDT
                )
            )
        else:
            _log(
                "恢复水位 baseline_id={} watching={} pending={} EXECUTE={} USDT_KEEP={} MIN_WD_USDT={}".format(
                    state["baseline_id"],
                    len(state.get("watching") or {}),
                    _PENDING,
                    EXECUTE,
                    USDT_KEEP_THRESHOLD,
                    MIN_WITHDRAW_USDT,
                )
            )
    finally:
        cursor.close()
        db.close()

    processed: Set[str] = set(state.get("processed_orders") or [])
    watching: Dict[str, dict] = dict(state.get("watching") or {})

    while True:
        db = None
        cursor = None
        try:
            db = connect_mysql()
            cursor = db.cursor()
            baseline = int(state["baseline_id"])
            news = fetch_new_orders(cursor, baseline)
            for o in news:
                oid = o["orderId"]
                if not oid or oid in processed or oid in watching:
                    continue
                if oid.startswith("error"):
                    continue
                watching[oid] = {
                    "id": o["id"],
                    "orderId": oid,
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "status": o["status"],
                    "fillsz": o["fillsz"],
                    "currency": o.get("currency") or "",
                    "price": o.get("price"),
                }
                _log(
                    "发现新订单 orderId={} symbol={} side={} status={} db_id={}".format(
                        oid, o["symbol"], o["side"], o["status"], o["id"]
                    )
                )

            if news:
                state["baseline_id"] = max(baseline, max(o["id"] for o in news))

            done_oids = []
            for oid, o in list(watching.items()):
                try:
                    finished = check_and_maybe_withdraw(o)
                except Exception as e:
                    _log("处理订单异常 orderId={} err={}".format(oid, e))
                    finished = False
                if finished:
                    done_oids.append(oid)

            for oid in done_oids:
                watching.pop(oid, None)
                processed.add(oid)

            state["watching"] = watching
            state["processed_orders"] = list(processed)
            save_state(state)
        except Exception as e:
            _log("主循环错误: {}".format(e))
        finally:
            if cursor is not None:
                cursor.close()
            if db is not None and db.is_connected():
                db.close()
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        _log("已退出")
        raise SystemExit(0)
