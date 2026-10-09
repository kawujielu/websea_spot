# -*- coding: utf-8 -*-
"""监控 hedge.orders：Gate 对冲单成交后，按买卖方向提回 Websea 196。

规则（与 bn_hedge_to_196_withdraw.py 一致）：
  1) 启动时只记水位，不做提币；仅处理启动后新出现的订单
  2) 按 orderId 查 Gate：FILLED/CLOSED，或 CANCELLED 且已成交量>0 → 触发
  3) BUY（用 USDT 买 coin）：提回数量 = 本笔订单成交量 base_filled（不是账户该币全部余额）
  4) SELL（把 coin 卖成 USDT）：
       - 若账户整体 USDT available < USDT_KEEP_THRESHOLD → 保留，不提
       - 若 >= 阈值 → 提回数量 = 本笔 quote_filled（本次卖出得到的 USDT）
  5) 实际提币 = min(本笔数量, 当前 available)，仅防可用不足；无链/地址配置则跳过

接口（Gate API v4）:
  GET  /api/v4/spot/accounts
  GET  /api/v4/spot/orders/{order_id}?currency_pair=XX_USDT
  POST /api/v4/withdrawals

  python gate_to_196_withdraw.py

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

MYSQL_HOST = "abc-mysql-instance-1.cr8a0xsju0u1.ap-southeast-1.rds.amazonaws.com"
MYSQL_USER = "admin"
MYSQL_PASSWORD = "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2"
MYSQL_DATABASE = "hedge"
MYSQL_PORT = 3306
TABLE_NAME = "orders"
EXCHANGE = "gate"

EXECUTE = True  # True 才真正提币
POLL_SEC = 10
REQUEST_TIMEOUT = 30
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gate_hedge_to_196_state.json"
)

# SELL 后：整体 USDT 低于此阈值则保留，不低于则提「本次」USDT（对齐 gate 补资告警 3000）
USDT_KEEP_THRESHOLD = 5000.0

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

# Gate: open/closed/cancelled → 归一后判断
TERMINAL_FULL = {"FILLED", "CLOSED"}
TERMINAL_PARTIAL_CANCEL = {"CANCELED", "CANCELLED"}
GATE_STATUS_MAP = {
    "open": "NEW",
    "closed": "FILLED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
}
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
    http_status = res.get("http_status")
    if http_status is not None:
        parts.append("http={}".format(http_status))
    body = res.get("body") if "body" in res else res
    if isinstance(body, dict):
        if body.get("label"):
            parts.append(str(body.get("label")))
        if body.get("message"):
            parts.append(str(body.get("message")))
        elif body.get("msg"):
            parts.append(str(body.get("msg")))
        if body.get("code") is not None and "http_status" not in res:
            parts.append("code={}".format(body.get("code")))
    elif body is not None:
        parts.append(str(body))
    if not parts:
        parts.append(str(res))
    return " | ".join(parts)


def _withdraw_ok(res: Any) -> bool:
    """Gate POST /withdrawals 成功：HTTP 2xx 且 body 含 id。"""
    if not isinstance(res, dict) or res.get("dry_run"):
        return False
    status = res.get("http_status")
    body = res.get("body")
    if not isinstance(status, int) or status < 200 or status >= 300:
        return False
    return isinstance(body, dict) and bool(body.get("id"))


def _notify_gate_to_196(
    coin: str,
    amount_s: str,
    network: str,
    address: str,
    *,
    ok: bool,
    fail_detail: str = "",
) -> None:
    """发起 Gate→196 提币后，成功/失败各只发一条 Telegram。"""
    title = "gate到196发起提币" if ok else "gate到196提币失败"
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
    biz_chain = COIN_CHAIN.get(coin)
    if not biz_chain:
        return None
    gate_chain = CHAIN_TO_GATE.get(biz_chain)
    addr_memo = ADDR_196.get(biz_chain)
    if not gate_chain or not addr_memo:
        return None
    address, memo = addr_memo
    return gate_chain, address, memo


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


def _normalize_status(status: str) -> str:
    raw = str(status or "").strip()
    mapped = GATE_STATUS_MAP.get(raw.lower())
    return (mapped or raw).upper()


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
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith(GATE_PREFIX):
        full_path = path
    else:
        full_path = GATE_PREFIX + path

    params = dict(params or {})
    query = "&".join("{}={}".format(k, params[k]) for k in params) if params else ""
    body_str = json.dumps(body) if body is not None else ""
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


def gate_get_order(symbol: str, order_id: str) -> Optional[dict]:
    """GET /spot/orders/{order_id}?currency_pair=ETH_USDT"""
    pair = str(symbol).replace("-", "_").upper()
    status, body = gate_request(
        "GET",
        "/spot/orders/{}".format(order_id),
        params={"currency_pair": pair},
    )
    if status != 200 or not isinstance(body, dict):
        return None
    return body


def gate_withdraw(
    currency: str,
    amount: float,
    chain: str,
    address: str,
    memo: Optional[str] = None,
) -> Any:
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
            currency, amt_s, chain, address, memo, EXECUTE
        )
    )
    if not EXECUTE:
        return {"dry_run": True, "payload": payload, "amount_s": amt_s}
    status, body = gate_request("POST", "/withdrawals", body=payload)
    return {"http_status": status, "body": body, "amount_s": amt_s}


def withdraw_coin(coin: str, amount: float) -> Any:
    """按本笔成交数量提币；send=min(本笔数量, available)，不会扫账户全额。"""
    cfg = _coin_withdraw_cfg(coin)
    if not cfg:
        _log("无196提币配置跳过 coin={} amount={}".format(coin, amount))
        return None
    bals = gate_spot_available()
    free = float(bals.get(coin.upper(), 0) or 0)
    send = min(float(amount), free)
    if send <= 0:
        _log("可用不足跳过 coin={} 本笔数量={} available={}".format(coin, amount, free))
        return None
    if send + 1e-12 < float(amount):
        _log(
            "本笔数量大于可用，按可用截断 coin={} 本笔={} available={} send={}".format(
                coin, amount, free, send
            )
        )
    chain, address, memo = cfg
    res = gate_withdraw(coin, send, chain, address, memo)
    _log(
        "提币结果 coin={} 本笔数量={} send={} available={} res={}".format(
            coin, amount, send, free, res
        )
    )
    # 真正发起提币后发一条 TG：成功/失败各只发一次（dry_run 不发）
    if EXECUTE and not (isinstance(res, dict) and res.get("dry_run")):
        amt_s = None
        if isinstance(res, dict):
            amt_s = res.get("amount_s")
        if not amt_s:
            amt_s = _fmt_amount(
                send, AMOUNT_DECIMALS.get(coin.upper(), DEFAULT_DECIMALS)
            ) or str(send)
        if _withdraw_ok(res):
            _notify_gate_to_196(coin, amt_s, chain, address, ok=True)
        else:
            _notify_gate_to_196(
                coin,
                amt_s,
                chain,
                address,
                ok=False,
                fail_detail=_fail_info(res),
            )
    return res


def _parse_gate_fills(go: dict) -> Tuple[float, float]:
    """
    返回 (base_filled, quote_filled)。
    Gate: filled_total 多为计价币成交额；base ≈ filled_total / avg_deal_price。
    """
    avg = float(go.get("avg_deal_price") or 0)
    filled_total = float(go.get("filled_total") or 0)
    # 部分返回还带 filled_amount（base）
    filled_amount = float(go.get("filled_amount") or 0)
    if filled_amount > 0:
        base = filled_amount
    elif avg > 0 and filled_total > 0:
        base = filled_total / avg
    else:
        base = 0.0
    quote = filled_total if filled_total > 0 else (base * avg if avg > 0 else 0.0)
    return base, quote


def order_is_done(status: str, executed_qty: float) -> bool:
    st = _normalize_status(status)
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
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"baseline_id": None, "processed_orders": [], "watching": {}}


def save_state(state: dict) -> None:
    processed = state.get("processed_orders") or []
    state["processed_orders"] = processed[-5000:]
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
        "SELECT id, orderId, exchange, symbol, side, amount, fillsz, status, currency "
        "FROM `{table}` WHERE exchange=%s AND id > %s ORDER BY id ASC"
    ).format(table=tbl)
    cursor.execute(sql, (EXCHANGE, after_id))
    cols = ["id", "orderId", "exchange", "symbol", "side", "amount", "fillsz", "status", "currency"]
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
        out.append(d)
    return out


def handle_filled_order(
    order: dict,
    go: Optional[dict],
    base_filled: float,
    quote_filled: float,
) -> None:
    side = str((go or {}).get("side") or order.get("side") or "").upper()
    symbol = order.get("symbol") or (go or {}).get("currency_pair") or ""
    base, quote = _base_quote_from_symbol(symbol)
    if order.get("currency"):
        base = str(order["currency"]).upper()

    if side == "BUY":
        # 用 USDT 买 coin → 只提本笔成交量 base_filled，不是账户该币全部余额
        _log(
            "BUY成交提币(本笔成交量) orderId={} symbol={} base={} 本笔base_filled={}".format(
                order.get("orderId"), symbol, base, base_filled
            )
        )
        withdraw_coin(base, base_filled)
        return

    if side == "SELL":
        bals = gate_spot_available()
        usdt_free = float(bals.get("USDT", 0) or 0)
        _log(
            "SELL成交 orderId={} symbol={} quote_filled={} usdt_available={} threshold={}".format(
                order.get("orderId"),
                symbol,
                quote_filled,
                usdt_free,
                USDT_KEEP_THRESHOLD,
            )
        )
        if usdt_free < USDT_KEEP_THRESHOLD:
            _log(
                "USDT低于阈值保留，不提币 usdt_available={} < {}".format(
                    usdt_free, USDT_KEEP_THRESHOLD
                )
            )
            return
        if quote_filled <= 0:
            _log("本次USDT成交额为0，跳过")
            return
        withdraw_coin("USDT", quote_filled)
        return

    _log("未知side，不提币 orderId={} side={}".format(order.get("orderId"), side))


def check_and_maybe_withdraw(order: dict) -> bool:
    oid = order["orderId"]
    symbol = order["symbol"]
    go = gate_get_order(symbol, oid)
    if go:
        status = _normalize_status(go.get("status") or "")
        base_filled, quote_filled = _parse_gate_fills(go)
        _log(
            "Gate订单 status orderId={} symbol={} side={} status={} "
            "base_filled={} quote_filled={} db_status={}".format(
                oid,
                symbol,
                go.get("side"),
                status,
                base_filled,
                quote_filled,
                order.get("status"),
            )
        )
    else:
        status = _normalize_status(order.get("status") or "")
        base_filled = float(order.get("fillsz") or 0)
        quote_filled = 0.0
        _log(
            "Gate查询失败，用库状态 orderId={} status={} fillsz={}".format(
                oid, status, base_filled
            )
        )

    st = status.upper()
    if st in {"NEW", "OPEN", "PARTIALLY_FILLED"}:
        return False

    if order_is_done(st, base_filled):
        _log(
            "触发提币判断 orderId={} status={} base_filled={}".format(
                oid, status, base_filled
            )
        )
        handle_filled_order(order, go, base_filled, quote_filled)
        # Gate 提现限频约 1r/3s
        time.sleep(0.2)
        return True

    if st in TERMINAL_PARTIAL_CANCEL | {"REJECTED", "FAILED"} and base_filled <= 0:
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
                "启动水位 baseline_id={}（此前订单不提币） EXECUTE={} USDT_KEEP={}".format(
                    state["baseline_id"], EXECUTE, USDT_KEEP_THRESHOLD
                )
            )
        else:
            _log(
                "恢复水位 baseline_id={} watching={} EXECUTE={} USDT_KEEP={}".format(
                    state["baseline_id"],
                    len(state.get("watching") or {}),
                    EXECUTE,
                    USDT_KEEP_THRESHOLD,
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
