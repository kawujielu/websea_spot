"""
批量购买外盘资产：拉取盘口卖一价，按固定 USDT 金额限价买入。
独立脚本，不导入 binance.py/gateio.py/kraken.py（避免 libs/load 依赖）。
仅依赖 aiohttp。

运行（Ubuntu 对冲服务器）:
  cd /home/ubuntu/code/spot_paddington/exchanges/restful_api
  python spot_depth_buy.py
"""
import asyncio
import base64
import csv
import hashlib
import hmac
import json
import math
import os
import time
import traceback
import urllib.parse
from operator import itemgetter

import aiohttp

# ---------- 固定参数（按需修改） ----------
REAL_ORDER = False  # True=真实下单，False=仅打印下单参数（默认）
ORDER_USDT = 100.0  # 每笔下单金额(USDT)
QUOTE = "USDT"
REQUEST_TIMEOUT = 15
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buy_assets.csv")

BN_URL = "https://api.binance.com"
GATE_URL = "https://api.gateio.ws"
KRAKEN_URL = "https://api.kraken.com"

BN_COINS = [
    "ORCA", "BMT", "HYPER", "KERNEL", "SXT", "NXPC", "NEWT", "ERA", "C", "SKY",
    "ESP", "MANTRA", "MASK", "GALA", "WLFI", "ETHFI", "PEPE", "WLD", "TON", "LTC",
    "CFX", "FLOKI", "ASTER", "PUMP", "USDC", "DOGE", "APE", "AXS", "ENS", "LINK",
    "MANA", "SAND", "SHIB", "COMP", "SUSHI", "1INCH", "AAVE", "CRV", "YGG", "ANKR",
    "BAT", "CHZ", "EGLD", "INJ", "IOTX", "QNT", "UNI", "TRB", "GLM", "TIA", "MEME",
    "FTT", "ORDI", "BEAMX", "CAKE", "GRT", "PEOPLE", "LDO", "GMT", "ONDO", "IMX",
    "PENDLE", "LPT", "JASMY", "SUI", "ARB", "AEVO", "ENA", "JTO", "NEAR", "JUP",
    "WIF", "BOME", "W", "RAY", "ZRO", "FET", "APT", "RENDER", "DOGS", "POL", "PNUT",
    "ACT", "NEIRO", "MOVE", "PENGU",
]
GATE_COINS = [
    "SAFE", "XAUT", "GIGGLE", "NVDAON", "AAPLON", "GOOGLON", "MSFTON", "TSLAON",
    "CRCLON", "AMDON", "KOON", "QQQON", "OKB",
]
KRAKEN_COINS = [
    # ("EURQ", "USD"),  # Kraken 无 EURQ/USDT，仅有 EURQ/USD、EURQ/EUR
]

BN_SYMBOL_MAP = {}
GATE_SYMBOL_MAP = {}
KRAKEN_SYMBOL_MAP = {}

BN_API_KEY = "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE"
BN_SECRET = "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU"
GATE_API_KEY = "dd0eeebf5f147b1c8c1cfb5c1db2f38f"
GATE_SECRET = "a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e"
KRAKEN_API_KEY = "Ac0cs+LmAdrvTDQ7VhiODdA3Oenn+ozumtgl2YsSy/gJLkHajSVe0hEp"
KRAKEN_SECRET = "LTMHPokskn9KcEjD+qgavfClZZE61t8oZTkayezzC22DDdQw0HXjxt1L32wS5ibNFB1BTXybirWnOAqu9PZYYQ=="


def _to_symbols(coins, mapping=None):
    mapping = mapping or {}
    out, seen = [], set()
    for coin in coins:
        base = coin.strip().upper()
        if not base or base in seen:
            continue
        seen.add(base)
        out.append("%s-%s" % (mapping.get(base, base), QUOTE))
    return out


BN_SYMBOLS = _to_symbols(BN_COINS, BN_SYMBOL_MAP)
GATE_SYMBOLS = _to_symbols(GATE_COINS, GATE_SYMBOL_MAP)


def _to_kraken_symbols(coins, mapping=None):
    """Kraken 支持 (基础币, 计价币) 元组，计价币默认 USDT。"""
    mapping = mapping or {}
    out, seen = [], set()
    for item in coins:
        if isinstance(item, (list, tuple)):
            base, quote = item[0], item[1]
        else:
            base, quote = item, QUOTE
        base = str(base).strip().upper()
        quote = str(quote).strip().upper()
        sym = "%s-%s" % (mapping.get(base, base), quote)
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


KRAKEN_SYMBOLS = _to_kraken_symbols(KRAKEN_COINS, KRAKEN_SYMBOL_MAP)


def round_down(number, precision):
    if precision <= 0:
        return int(number)
    return round(int(number * 10 ** precision) / 10 ** precision, precision)


def fmt_price(price, precision):
    if precision <= 0:
        return str(int(price))
    return ("%%.%df" % precision) % round(price, precision)


def _bn_order_params(data):
    has_signature = False
    params = []
    for key, value in data.items():
        if key == "signature":
            has_signature = True
        else:
            params.append((key, value))
    params.sort(key=itemgetter(0))
    if has_signature:
        params.append(("signature", data["signature"]))
    return params


def _bn_sign(secret, params):
    ordered = _bn_order_params(params)
    qs = "&".join("%s=%s" % (k, v) for k, v in ordered)
    return hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()


def _gate_sign(secret, method, path, ts, query, body):
    payload_hash = hashlib.sha512((body or "").encode()).hexdigest()
    msg = "%s\n%s\n%s\n%s\n%s" % (method, path, query, payload_hash, ts)
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha512).hexdigest()


def _kraken_sign(secret, path, data, nonce):
    post_data = urllib.parse.urlencode(data)
    encoded = (str(nonce) + post_data).encode()
    message = path.encode() + hashlib.sha256(encoded).digest()
    return base64.b64encode(
        hmac.new(base64.b64decode(secret), message, hashlib.sha512).digest()
    ).decode()


class BinanceLite:
    def __init__(self, session, api_key, secret, base_url=BN_URL):
        self.session, self.api_key, self.secret = session, api_key, secret
        self.url = base_url.rstrip("/")
        self._prec = {}

    async def _request(self, method, path, params, signed=False):
        params = dict(params)
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = _bn_sign(self.secret, params)
        ordered = _bn_order_params(params)
        ordered = [(k, v) for k, v in ordered if v is not None]
        query_string = "&".join("%s=%s" % (k, v) for k, v in ordered)
        url = self.url + path
        if query_string:
            url = url + "?" + query_string
        headers = {
            "Accept": "application/json",
            "User-Agent": "binance/python",
            "X-MBX-APIKEY": self.api_key,
        }
        async with self.session.request(method, url, headers=headers, timeout=REQUEST_TIMEOUT) as r:
            text = await r.text()
            return r.status, json.loads(text) if text else {}

    async def depth(self, symbol, limit=5):
        status, data = await self._request("GET", "/api/v3/depth", {
            "symbol": symbol.replace("-", ""), "limit": limit,
        })
        if status != 200:
            return {"code": status, "content": data}
        return data

    async def _precision(self, symbol):
        if symbol in self._prec:
            return self._prec[symbol]
        status, data = await self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol.replace("-", "")})
        if status != 200:
            raise RuntimeError("BN precision %s: %s" % (symbol, data))
        filters = {f["filterType"]: f for f in data["symbols"][0]["filters"]}
        tick = float(filters["PRICE_FILTER"]["tickSize"])
        step = float(filters["LOT_SIZE"]["stepSize"])
        prec = {
            "price_precision": max(0, -math.ceil(math.log10(tick))),
            "amount_precision": max(0, -math.ceil(math.log10(step))),
            "minQty": float(filters["LOT_SIZE"]["minQty"]),
            "minQtyQuote": float(filters.get("NOTIONAL", {}).get("minNotional", 0)),
        }
        self._prec[symbol] = prec
        return prec

    async def create_order(self, symbol, side, amount, price, type="LIMIT", timeInForce="GTC"):
        prec = await self._precision(symbol)
        amount = round_down(amount, prec["amount_precision"])
        price = fmt_price(price, prec["price_precision"])
        status, data = await self._request("POST", "/api/v3/order", {
            "symbol": symbol.replace("-", ""), "side": side, "type": type,
            "timeInForce": timeInForce, "quantity": str(amount), "price": price,
        }, signed=True)
        if status != 200:
            return {"code": 400, "content": data}
        return data


class GateLite:
    def __init__(self, session, api_key, secret, base_url=GATE_URL):
        self.session, self.api_key, self.secret = session, api_key, secret
        self.url = base_url.rstrip("/")
        self._prec = {}

    async def _request(self, method, path, params=None, body=None, signed=True):
        params = params or {}
        query = "&".join("%s=%s" % (k, v) for k, v in params.items()) if method != "POST" else ""
        body_str = json.dumps(body) if body else ""
        full_path = "/api/v4" + path
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if signed:
            ts = str(time.time())
            headers["KEY"] = self.api_key
            headers["Timestamp"] = ts
            headers["SIGN"] = _gate_sign(self.secret, method, full_path, ts, query, body_str)
        if method == "POST":
            url = self.url + full_path
            async with self.session.request(method, url, data=body_str, headers=headers, timeout=REQUEST_TIMEOUT) as r:
                text = await r.text()
                return r.status, json.loads(text) if text else {}
        url = self.url + full_path + ("?" + query if query else "")
        async with self.session.request(method, url, headers=headers, timeout=REQUEST_TIMEOUT) as r:
            text = await r.text()
            return r.status, json.loads(text) if text else {}

    async def depth(self, symbol, limit=5):
        status, data = await self._request("GET", "/spot/order_book", {
            "currency_pair": symbol.replace("-", "_"), "limit": limit,
        }, signed=False)
        if status != 200:
            return {"code": status, "content": data}
        return data

    async def _precision(self, symbol):
        if symbol in self._prec:
            return self._prec[symbol]
        pair = symbol.replace("-", "_")
        status, data = await self._request("GET", "/spot/currency_pairs/%s" % pair, signed=False)
        if status != 200:
            raise RuntimeError("Gate precision %s: %s" % (symbol, data))
        prec = {
            "price_precision": data["precision"],
            "amount_precision": data["amount_precision"],
            "minQty": float(data.get("min_base_amount") or 0),
            "minQtyQuote": float(data.get("min_quote_amount") or 0),
        }
        self._prec[symbol] = prec
        return prec

    async def create_order(self, symbol, side, amount, price, type="limit", account="spot"):
        prec = await self._precision(symbol)
        amount = round_down(amount, prec["amount_precision"])
        price = fmt_price(price, prec["price_precision"])
        body = {
            "currency_pair": symbol.replace("-", "_"), "account": account,
            "side": side.lower(), "type": type, "amount": str(amount), "price": price,
        }
        status, data = await self._request("POST", "/spot/orders", body=body)
        if status not in (200, 201):
            return {"code": 400, "content": data}
        data["orderId"] = data.get("id")
        return data


class KrakenLite:
    def __init__(self, session, api_key, secret, base_url=KRAKEN_URL):
        self.session, self.api_key, self.secret = session, api_key, secret
        self.url = base_url.rstrip("/")
        self._prec = {}
        self._pair_cache = {}

    def _pair(self, symbol):
        """EURQ-USD -> EURQUSD（Kraken altname）"""
        if symbol in self._pair_cache:
            return self._pair_cache[symbol]
        pair = symbol.replace("-", "")
        self._pair_cache[symbol] = pair
        return pair

    async def _request(self, method, endpoint, data=None, signed=False):
        data = dict(data or {})
        get_path = "" if method == "POST" else ("?" + urllib.parse.urlencode(data) if data else "")
        url = self.url + endpoint + get_path
        headers = {"User-Agent": "Kraken Python Client", "Content-Type": "application/x-www-form-urlencoded"}
        body = None
        if signed:
            nonce = str(int(time.time() * 1000))
            data["nonce"] = nonce
            headers["API-Key"] = self.api_key
            headers["API-Sign"] = _kraken_sign(self.secret, endpoint, data, nonce)
            body = urllib.parse.urlencode(data)
        async with self.session.request(
            method, url, headers=headers, data=body, timeout=REQUEST_TIMEOUT,
        ) as r:
            text = await r.text()
            return r.status, json.loads(text) if text else {}

    async def depth(self, symbol, limit=5):
        pair = self._pair(symbol)
        status, data = await self._request("GET", "/0/public/Depth", {"pair": pair, "count": limit})
        if status != 200 or data.get("error"):
            hint = ""
            if data.get("error") == ["EQuery:Unknown asset pair"]:
                hint = "（请检查 KRAKEN_COINS 计价币，如 EURQ 用 USD 而非 USDT）"
            return {"code": 400, "content": data.get("error", data), "hint": hint}
        market = list(data["result"].values())[0]
        return {
            "asks": [[float(p), float(a)] for p, a, _ in market["asks"]],
            "bids": [[float(p), float(a)] for p, a, _ in market["bids"]],
        }

    async def _precision(self, symbol):
        if symbol in self._prec:
            return self._prec[symbol]
        pair = self._pair(symbol)
        status, data = await self._request("GET", "/0/public/AssetPairs", {"pair": pair})
        if status != 200 or data.get("error"):
            raise RuntimeError("Kraken precision %s: %s" % (symbol, data))
        pair = list(data["result"].values())[0]
        prec = {
            "price_precision": pair["pair_decimals"],
            "amount_precision": pair["lot_decimals"],
            "minQty": float(pair["ordermin"]),
            "minQtyQuote": 0.0001,
        }
        self._prec[symbol] = prec
        return prec

    async def create_order(self, symbol, side, amount, price, type="limit", force="gtc"):
        prec = await self._precision(symbol)
        amount = round_down(amount, prec["amount_precision"])
        price = fmt_price(price, prec["price_precision"])
        payload = {
            "pair": self._pair(symbol), "type": side.lower(),
            "ordertype": type.lower(), "volume": str(amount), "price": price,
        }
        status, data = await self._request("POST", "/0/private/AddOrder", payload, signed=True)
        if status != 200 or data.get("error"):
            return {"code": 400, "content": data.get("error", data)}
        return {"orderId": data["result"]["txid"][0], "status": "NEW"}


async def _buy(api, symbol, usdt, tag):
    depth = await api.depth(symbol)
    if not isinstance(depth, dict) or not depth.get("asks"):
        hint = depth.get("hint", "") if isinstance(depth, dict) else ""
        raise RuntimeError("%s depth %s 无效: %s%s" % (tag, symbol, depth, hint))
    ask = float(depth["asks"][0][0])
    amount = usdt / ask
    params = {"exchange": tag, "symbol": symbol, "side": "BUY", "amount": amount, "price": ask, "usdt": usdt}
    if not REAL_ORDER:
        print("[DRY-RUN] %s" % params)
        return dict(params, orderId=None, dry_run=True)
    order = await api.create_order(symbol, "BUY", amount, ask)
    if isinstance(order, dict) and order.get("code") == 400:
        raise RuntimeError("%s 下单失败 %s: %s" % (tag, symbol, order.get("content", order)))
    oid = order.get("orderId") or order.get("id")
    print("[%s] %s BUY @ %s orderId=%s" % (tag, symbol, ask, oid))
    return dict(params, orderId=oid, dry_run=False)


async def run():
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        bn = BinanceLite(session, BN_API_KEY, BN_SECRET)
        gate = GateLite(session, GATE_API_KEY, GATE_SECRET)
        kraken = KrakenLite(session, KRAKEN_API_KEY, KRAKEN_SECRET)
        results = []
        for sym in BN_SYMBOLS:
            try:
                results.append(await _buy(bn, sym, ORDER_USDT, "bn"))
            except Exception:
                print("BN %s 异常:\n%s" % (sym, traceback.format_exc()))
        for sym in GATE_SYMBOLS:
            try:
                results.append(await _buy(gate, sym, ORDER_USDT, "gate"))
            except Exception:
                print("Gate %s 异常:\n%s" % (sym, traceback.format_exc()))
        for sym in KRAKEN_SYMBOLS:
            try:
                results.append(await _buy(kraken, sym, ORDER_USDT, "kraken"))
            except Exception:
                print("Kraken %s 异常:\n%s" % (sym, traceback.format_exc()))
        return results


def _save_csv(results):
    rows = []
    for r in results:
        if not r or "symbol" not in r:
            continue
        rows.append({
            "coin": r["symbol"].split("-")[0].upper(),
            "vol": r["amount"],
            "amt": r["usdt"],
        })
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["coin", "vol", "amt"])
        writer.writeheader()
        writer.writerows(rows)
    print("已保存 %d 条到 %s" % (len(rows), OUTPUT_CSV))


def main():
    mode = "真实下单" if REAL_ORDER else "仅打印参数"
    print("模式: %s | ORDER_USDT=%s" % (mode, ORDER_USDT))
    results = asyncio.run(run())
    _save_csv(results)
    for r in results:
        if r.get("dry_run"):
            continue
        print("[%s] %s BUY amount=%s @ %s orderId=%s" % (
            r["exchange"], r["symbol"], r["amount"], r["price"], r["orderId"],
        ))


if __name__ == "__main__":
    main()
