"""
从 scripts/币币缺口.xlsx 读取币种与数量，拉取 Gate 现货 USDT 交易对卖一价并估算下单金额。

Gate API 凭证与 engine/position_hedge.py 对冲一致：
  many_configs.account_config.EXTERNAL_ACCOUNTS['gate']（生产经 libs 拉取 abclibs）
  可通过环境变量 GATE_API_KEY / GATE_SECRET 或 --api-key / --secret 覆盖。

运行（在 spot_paddington 项目根目录）:
  python scripts/gate_gap_depth_quote.py
  python scripts/gate_gap_depth_quote.py --place-orders
  python scripts/gate_gap_depth_quote.py --place-orders --slippage 0.002 --order-interval 0.5

下单说明（需加 --place-orders）:
  - 缺口数量为负 → 买入；限价 = 卖一价 × (1 + 滑点)，默认滑点千2 (0.002)
  - 逐笔下单，默认间隔 0.5 秒

依赖:
  pip install aiohttp pandas openpyxl
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from pathlib import Path
from typing import Any

import aiohttp

API_PREFIX = "/api/v4"
DEFAULT_SLIPPAGE = Decimal("0.002")  # 千2
DEFAULT_ORDER_INTERVAL_S = 0.5
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXCEL = SCRIPT_DIR / "币币缺口.xlsx"
PROJECT_ROOT = SCRIPT_DIR.parent

COIN_HEADER_HINTS = ("coin", "币种", "货币", "symbol", "token", "currency", "币种名称", "货币名称")
AMOUNT_HEADER_HINTS = ("amount", "数量", "缺口", "qty", "quantity", "数目", "volume", "缺口数量")


@dataclass
class CoinRow:
    coin: str
    amount: Decimal


@dataclass
class QuoteRow:
    coin: str
    pair: str
    amount: Decimal
    ask1_price: Decimal | None
    order_usdt: Decimal | None
    error: str | None = None
    side: str | None = None
    limit_price: Decimal | None = None
    order_id: str | None = None
    place_error: str | None = None


@dataclass
class GateContext:
    """对冲 Gate 账户上下文（凭证来源与 GateioApi 一致）。"""

    api_key: str
    secret: str
    base_url: str
    cred_source: str


def _normalize_header(cell: object) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", "", str(cell).strip().lower())


def _parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float):
        import math

        if math.isnan(value) or math.isinf(value):
            return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        value = text
    try:
        amount = Decimal(str(value))
    except Exception:
        return None
    if not amount.is_finite() or amount == 0:
        return None
    return amount


def _parse_coin(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        import math

        if math.isnan(value):
            return None
    text = str(value).strip().upper()
    if not text or text in ("NAN", "NONE", "NULL"):
        return None
    text = text.split("/")[0].split("-")[0].split("_")[0]
    if not re.fullmatch(r"[A-Z0-9]{1,20}", text):
        return None
    return text or None


def _detect_columns(headers: list[object]) -> tuple[int, int] | None:
    coin_idx = amount_idx = None
    for i, h in enumerate(headers):
        nh = _normalize_header(h)
        if not nh:
            continue
        if any(k in nh for k in COIN_HEADER_HINTS):
            coin_idx = i
        if any(k in nh for k in AMOUNT_HEADER_HINTS):
            amount_idx = i
    if coin_idx is not None and amount_idx is not None and coin_idx != amount_idx:
        return coin_idx, amount_idx
    return None


def _row_looks_like_data(series) -> bool:
    coin = _parse_coin(series.iloc[0])
    amount = _parse_amount(series.iloc[1]) if len(series) > 1 else None
    return coin is not None and amount is not None and amount != 0


def load_coins_from_excel(path: Path, sheet: str | int) -> list[CoinRow]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("缺少 pandas，请执行: pip install pandas openpyxl") from exc

    if not path.is_file():
        raise SystemExit(f"Excel 文件不存在: {path}")

    df = pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")
    if df.empty:
        raise SystemExit("Excel 为空")

    coin_idx, amount_idx = 0, 1
    if df.shape[1] < 2:
        raise SystemExit("无法识别列：请使用「币种 + 数量」两列，或带表头（币种/数量）")

    headers = df.iloc[0].tolist()
    detected = _detect_columns(headers)
    if detected is not None:
        coin_idx, amount_idx = detected
        start_row = 1
    elif _row_looks_like_data(df.iloc[0]):
        start_row = 0
    else:
        start_row = 1

    rows: list[CoinRow] = []
    merged: dict[str, Decimal] = {}
    for _, series in df.iloc[start_row:].iterrows():
        coin = _parse_coin(series.iloc[coin_idx])
        amount = _parse_amount(series.iloc[amount_idx])
        if coin is None or amount is None:
            continue
        merged[coin] = merged.get(coin, Decimal(0)) + amount

    for coin, amount in sorted(merged.items()):
        rows.append(CoinRow(coin=coin, amount=amount))
    if not rows:
        raise SystemExit("未从 Excel 解析到有效币种与数量")
    return rows


def _to_gate_pair(coin: str) -> str:
    if coin == "USDT":
        return "USDT_USDT"
    return f"{coin}_USDT"


def _ensure_project_root() -> None:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _bootstrap_libs_debug_if_needed() -> None:
    """本机无 load 时模拟 libs.DEBUG=True，与 account_config 测试账户一致。"""
    import types

    if "load" in sys.modules:
        return
    try:
        import load  # noqa: F401
    except ModuleNotFoundError:
        load_mod = types.ModuleType("load")
        load_mod.load_remote = types.ModuleType("load.load_remote")
        sys.modules["load"] = load_mod
        libs_mod = types.ModuleType("libs")
        libs_mod.libs_config = types.SimpleNamespace(DEBUG=True)
        libs_mod.libs_ex_account = {}
        sys.modules["libs"] = libs_mod


def _load_external_accounts() -> dict:
    """与 GateioApi 相同：EXTERNAL_ACCOUNTS（生产经 libs.libs_ex_account）。"""
    _ensure_project_root()
    _bootstrap_libs_debug_if_needed()
    for mod_name in ("many_configs.account_config", "many_configs"):
        sys.modules.pop(mod_name, None)
    from many_configs.account_config import EXTERNAL_ACCOUNTS

    return EXTERNAL_ACCOUNTS


def _resolve_gate_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    """与 GateioApi / position_hedge 一致：CLI > 环境变量 > EXTERNAL_ACCOUNTS['gate']。"""
    key = 'dd0eeebf5f147b1c8c1cfb5c1db2f38f'   # getattr(args, "api_key", None) or os.environ.get("GATE_API_KEY")
    secret = 'a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e'   # getattr(args, "secret", None) or os.environ.get("GATE_SECRET")
    if key and secret:
        return key, secret, "命令行/环境变量"

    external = _load_external_accounts()
    gate = external.get("gate")
    if not gate:
        raise SystemExit("EXTERNAL_ACCOUNTS 中未找到 gate 配置")
    key = gate.get("apiKey") or gate.get("api_key")
    secret = gate.get("secret")
    if not key or not secret:
        raise SystemExit("EXTERNAL_ACCOUNTS['gate'] 缺少 apiKey 或 secret")
    return key, secret, "many_configs.account_config.EXTERNAL_ACCOUNTS['gate']"


def _gate_rest_base_url(override: str | None) -> str:
    if override:
        return override.rstrip("/")
    _ensure_project_root()
    _bootstrap_libs_debug_if_needed()
    sys.modules.pop("many_configs.exchange_config", None)
    from many_configs.exchange_config import EXCHANGE_CONFIG

    return EXCHANGE_CONFIG["gate"]["spot_restful"].rstrip("/")


def _build_gate_context(args: argparse.Namespace) -> GateContext:
    api_key, secret, cred_source = _resolve_gate_credentials(args)
    base_url = _gate_rest_base_url(getattr(args, "base_url", None))
    return GateContext(api_key=api_key, secret=secret, base_url=base_url, cred_source=cred_source)


def _parse_params_to_str(data: dict) -> str:
    if not data:
        return ""
    return "&".join(f"{k}={v}" for k, v in data.items())


def _gen_sign(secret: str, method: str, url_path: str, t: str, query_string: str, payload_string: str) -> str:
    m = hashlib.sha512()
    m.update((payload_string or "").encode("utf-8"))
    hashed_payload = m.hexdigest()
    s = "%s\n%s\n%s\n%s\n%s" % (method, url_path, query_string or "", hashed_payload, t)
    return hmac.new(secret.encode("utf-8"), s.encode("utf-8"), hashlib.sha512).hexdigest()


@dataclass
class PairPrecision:
    price_precision: int
    amount_precision: int
    min_base: Decimal
    min_quote: Decimal


class GateSpotClient:
    """Gate 现货 REST（签名逻辑与 gateio.GateioApi / run_gate_wallet 一致）。"""

    def __init__(self, session: aiohttp.ClientSession, gate: GateContext):
        self._session = session
        self._gate = gate
        self._precision_cache: dict[str, PairPrecision] = {}

    async def _request(
        self, path: str, method: str, data: dict | None, *, signed: bool, timeout: int = 15
    ) -> dict[str, Any]:
        data = data or {}
        query_string = "" if method == "POST" else _parse_params_to_str(data)
        body = json.dumps(data) if method == "POST" else ""
        full_path = f"{API_PREFIX}{path}"
        timestamp = str(time.time())
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if signed:
            headers["KEY"] = self._gate.api_key
            headers["Timestamp"] = timestamp
            headers["SIGN"] = _gen_sign(
                self._gate.secret, method, full_path, timestamp, query_string, body
            )
        if method == "GET":
            url = f"{self._gate.base_url}{full_path}"
            if query_string:
                url = f"{url}?{query_string}"
            async with self._session.request(method, url, headers=headers, timeout=timeout) as r:
                return {"code": r.status, "content": await r.text()}
        async with self._session.request(
            method, f"{self._gate.base_url}{full_path}", data=body, headers=headers, timeout=timeout
        ) as r:
            return {"code": r.status, "content": await r.text()}

    async def fetch_order_book(self, pair: str, limit: int = 1) -> dict:
        result = await self._request(
            "/spot/order_book",
            "GET",
            {"currency_pair": pair, "limit": limit},
            signed=False,
        )
        if result["code"] != 200:
            raise RuntimeError(f"HTTP {result['code']}: {result['content'][:200]}")
        return json.loads(result["content"])

    async def fetch_precision(self, pair: str) -> PairPrecision:
        if pair in self._precision_cache:
            return self._precision_cache[pair]
        result = await self._request(
            f"/spot/currency_pairs/{pair}",
            "GET",
            {},
            signed=False,
        )
        if result["code"] != 200:
            raise RuntimeError(f"精度查询失败 {pair}: {result['content'][:200]}")
        content = json.loads(result["content"])
        prec = PairPrecision(
            price_precision=int(content["precision"]),
            amount_precision=int(content["amount_precision"]),
            min_base=Decimal(str(content.get("min_base_amount") or 0)),
            min_quote=Decimal(str(content.get("min_quote_amount") or 0)),
        )
        self._precision_cache[pair] = prec
        return prec

    async def create_limit_order(
        self, pair: str, side: str, amount: Decimal, price: Decimal
    ) -> dict[str, Any]:
        prec = await self.fetch_precision(pair)
        amount = _round_decimal(amount, prec.amount_precision, ROUND_DOWN)
        price_round = ROUND_UP if side.lower() == "buy" else ROUND_DOWN
        price = _round_decimal(price, prec.price_precision, price_round)
        if amount <= 0:
            return {"code": 400, "content": json.dumps({"label": "INVALID_PARAM", "message": "amount<=0"})}
        if prec.min_base > 0 and amount < prec.min_base:
            return {
                "code": 400,
                "content": json.dumps({"message": f"amount {amount} < min_base {prec.min_base}"}),
            }
        if prec.min_quote > 0 and amount * price < prec.min_quote:
            return {
                "code": 400,
                "content": json.dumps(
                    {"message": f"notional {amount * price} < min_quote {prec.min_quote}"}
                ),
            }
        payload = {
            "currency_pair": pair,
            "account": "spot",
            "side": side.lower(),
            "type": "limit",
            "amount": _decimal_to_str(amount),
            "price": _decimal_to_str(price),
        }
        return await self._request("/spot/orders", "POST", payload, signed=True)


def _decimal_to_str(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _round_decimal(value: Decimal, places: int, rounding=ROUND_DOWN) -> Decimal:
    if places <= 0:
        return value.quantize(Decimal(1), rounding=rounding)
    quant = Decimal(10) ** -places
    return value.quantize(quant, rounding=rounding)


def _order_side(amount: Decimal) -> str:
    return "buy" if amount < 0 else "sell"


def _limit_price_with_slippage(ask1: Decimal, side: str, slippage: Decimal) -> Decimal:
    """买单：卖一价 + 千二滑点；卖单：卖一价 - 滑点。"""
    if side == "buy":
        return ask1 * (Decimal(1) + slippage)
    return ask1 * (Decimal(1) - slippage)


def _apply_quote_meta(q: QuoteRow, slippage: Decimal) -> None:
    if q.ask1_price is None or q.error:
        return
    if q.coin == "USDT":
        return
    q.side = _order_side(q.amount)
    q.limit_price = _limit_price_with_slippage(q.ask1_price, q.side, slippage)


async def _quote_one(
    client: GateSpotClient,
    row: CoinRow,
    sem: asyncio.Semaphore,
) -> QuoteRow:
    pair = _to_gate_pair(row.coin)
    if row.coin == "USDT":
        return QuoteRow(
            coin=row.coin,
            pair=pair,
            amount=row.amount,
            ask1_price=Decimal(1),
            order_usdt=abs(row.amount),
        )

    async with sem:
        try:
            book = await client.fetch_order_book(pair)
        except Exception as exc:
            return QuoteRow(
                coin=row.coin,
                pair=pair,
                amount=row.amount,
                ask1_price=None,
                order_usdt=None,
                error=str(exc),
            )

    asks = book.get("asks") or []
    if not asks:
        return QuoteRow(
            coin=row.coin,
            pair=pair,
            amount=row.amount,
            ask1_price=None,
            order_usdt=None,
            error="无卖盘",
        )

    try:
        ask1 = Decimal(str(asks[0][0]))
    except Exception:
        return QuoteRow(
            coin=row.coin,
            pair=pair,
            amount=row.amount,
            ask1_price=None,
            order_usdt=None,
            error="卖一价格解析失败",
        )

    order_usdt = abs(row.amount) * ask1
    quote = QuoteRow(
        coin=row.coin,
        pair=pair,
        amount=row.amount,
        ask1_price=ask1,
        order_usdt=order_usdt,
    )
    return quote


async def fetch_quotes(
    coins: list[CoinRow],
    gate: GateContext,
    concurrency: int,
) -> list[QuoteRow]:
    sem = asyncio.Semaphore(max(1, concurrency))
    connector = aiohttp.TCPConnector(limit=concurrency + 2, ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = GateSpotClient(session, gate)
        tasks = [_quote_one(client, row, sem) for row in coins]
        return list(await asyncio.gather(*tasks))


def _fmt_decimal(value: Decimal | None, places: int = 8) -> str:
    if value is None:
        return "-"
    q = value.quantize(Decimal(10) ** -places)
    text = format(q.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def print_report(quotes: list[QuoteRow], *, show_order_cols: bool = False) -> Decimal:
    if show_order_cols:
        headers = ("交易对", "币种", "数量", "卖一价", "方向", "限价(卖一+滑点)", "下单金额(USDT)", "备注")
        col_widths = [16, 8, 18, 14, 6, 18, 18, 20]
    else:
        headers = ("交易对", "币种", "数量", "卖一价", "下单金额(USDT)", "备注")
        col_widths = [16, 8, 18, 16, 20, 24]
    line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(line)
    print("-" * len(line))

    total = Decimal(0)
    ok_count = 0
    for q in sorted(quotes, key=lambda x: x.coin):
        pair_show = q.pair.replace("_", "-")
        note = q.error or ""
        if q.order_usdt is not None and q.error is None:
            total += q.order_usdt
            ok_count += 1
        if show_order_cols:
            cells = [
                pair_show.ljust(col_widths[0]),
                q.coin.ljust(col_widths[1]),
                _fmt_decimal(q.amount).ljust(col_widths[2]),
                _fmt_decimal(q.ask1_price).ljust(col_widths[3]),
                (q.side or "-").ljust(col_widths[4]),
                _fmt_decimal(q.limit_price).ljust(col_widths[5]),
                _fmt_decimal(q.order_usdt, places=2).ljust(col_widths[6]),
                note[: col_widths[7]].ljust(col_widths[7]),
            ]
        else:
            cells = [
                pair_show.ljust(col_widths[0]),
                q.coin.ljust(col_widths[1]),
                _fmt_decimal(q.amount).ljust(col_widths[2]),
                _fmt_decimal(q.ask1_price).ljust(col_widths[3]),
                _fmt_decimal(q.order_usdt, places=2).ljust(col_widths[4]),
                note[: col_widths[5]].ljust(col_widths[5]),
            ]
        print(" | ".join(cells))

    print("-" * len(line))
    print(f"成功计价: {ok_count}/{len(quotes)} 个币种")
    print(f"下单金额合计 (USDT): {_fmt_decimal(total, places=2)}")
    return total


def print_place_report(quotes: list[QuoteRow], slippage: Decimal) -> None:
    headers = ("交易对", "方向", "数量", "卖一价", "限价(含滑点)", "订单ID", "备注")
    col_widths = [16, 6, 18, 14, 16, 14, 28]
    line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print("\n" + line)
    print("-" * len(line))
    ok = 0
    for q in sorted(quotes, key=lambda x: x.coin):
        if q.coin == "USDT":
            continue
        pair_show = q.pair.replace("_", "-")
        note = q.place_error or q.error or ""
        if q.order_id and not q.place_error:
            ok += 1
            note = "ok"
        print(
            " | ".join(
                [
                    pair_show.ljust(col_widths[0]),
                    (q.side or "-").ljust(col_widths[1]),
                    _fmt_decimal(abs(q.amount)).ljust(col_widths[2]),
                    _fmt_decimal(q.ask1_price).ljust(col_widths[3]),
                    _fmt_decimal(q.limit_price).ljust(col_widths[4]),
                    (q.order_id or "-").ljust(col_widths[5]),
                    note[: col_widths[6]].ljust(col_widths[6]),
                ]
            )
        )
    print("-" * len(line))
    print(f"滑点: {slippage * 1000}‰ | 下单成功: {ok}")


async def place_orders_sequential(
    quotes: list[QuoteRow],
    gate: GateContext,
    *,
    interval_s: float,
) -> list[QuoteRow]:
    connector = aiohttp.TCPConnector(limit=5, ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = GateSpotClient(session, gate)
        ordered = sorted(quotes, key=lambda x: x.coin)
        for i, q in enumerate(ordered):
            if q.coin == "USDT":
                q.place_error = "跳过 USDT"
                continue
            if q.error or q.ask1_price is None or not q.side or not q.limit_price:
                q.place_error = q.error or "无有效报价"
                continue
            pair_show = q.pair.replace("_", "-")
            try:
                result = await client.create_limit_order(
                    q.pair, q.side, abs(q.amount), q.limit_price
                )
                print(f"{pair_show}: {result['content']}")
            except Exception as exc:
                print(f"{pair_show}: 请求异常 {exc}")
                q.place_error = str(exc)
            else:
                if result["code"] in (200, 201):
                    data = json.loads(result["content"])
                    q.order_id = str(data.get("id", ""))
                else:
                    q.place_error = result["content"][:200]
            if i < len(ordered) - 1:
                await asyncio.sleep(interval_s)
    return quotes


def _configure_stdout() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    _configure_stdout()
    p = argparse.ArgumentParser(description="币币缺口 Excel + Gate 现货 USDT 卖一估价")
    p.add_argument(
        "--excel",
        type=Path,
        default=Path(os.environ.get("GAP_EXCEL_PATH", str(DEFAULT_EXCEL))),
        help=f"缺口 Excel 路径，默认 {DEFAULT_EXCEL}",
    )
    p.add_argument("--sheet", default=0, help="工作表名或索引，默认第一个表")
    p.add_argument(
        "--base-url",
        default=os.environ.get("GATE_SPOT_RESTFUL"),
        help="覆盖 Gate REST 根地址；默认使用 exchange_config 中 gate.spot_restful",
    )
    p.add_argument("--api-key", default=None, help="覆盖 EXTERNAL_ACCOUNTS gate apiKey")
    p.add_argument("--secret", default=None, help="覆盖 EXTERNAL_ACCOUNTS gate secret")
    p.add_argument("--concurrency", type=int, default=10, help="并发请求深度上限")
    p.add_argument(
        "--place-orders",
        action="store_true",
        help="拉取卖一后按限价在 Gate 下单（默认仅估价不下单）",
    )
    p.add_argument(
        "--slippage",
        type=float,
        default=float(DEFAULT_SLIPPAGE),
        help="相对卖一价的滑点比例，默认 0.002（千2）",
    )
    p.add_argument(
        "--order-interval",
        type=float,
        default=DEFAULT_ORDER_INTERVAL_S,
        help="每笔下单间隔秒数，默认 0.5",
    )
    args = p.parse_args()
    slippage = Decimal(str(args.slippage))

    gate = _build_gate_context(args)
    print(f"Gate 凭证来源: {gate.cred_source} (apiKey={_mask_secret(gate.api_key)})")
    print(f"Gate REST: {gate.base_url}\n")

    sheet: str | int = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    coins = load_coins_from_excel(args.excel, sheet)
    print(f"已从 {args.excel} 读取 {len(coins)} 个币种\n")
    quotes = asyncio.run(fetch_quotes(coins, gate, args.concurrency))
    for q in quotes:
        _apply_quote_meta(q, slippage)
    print_report(quotes, show_order_cols=args.place_orders)

    if args.place_orders:
        print(f"\n开始 Gate 限价下单（卖一 + {slippage * 1000}‰ 滑点，每笔间隔 {args.order_interval}s）...")
        quotes = asyncio.run(
            place_orders_sequential(
                quotes,
                gate,
                interval_s=args.order_interval,
            )
        )
        print_place_report(quotes, slippage)


if __name__ == "__main__":
    main()
