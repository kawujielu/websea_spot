# -*- coding: utf-8 -*-
"""
功能:
  拉取 Gate 现货 AAPLX / NVDAX / TSLAX 与 Bitget 现货 AAPLON / NVDAON / TSLAON 的
  盘口价差比例、2% 深度（买卖两侧 USDT 名义），以及 10000 USDT 市价买入的滑点比例。
  价差/滑点均为相对中间价的无量纲比例，例如 0.000740 表示 0.074%。

参数:
  DEPTH_PCT = 0.02           — 深度带宽：中间价上下 2%
  MARKET_BUY_USDT = 10000.0  — 市价买入花费的 USDT 名义
  ORDERBOOK_LIMIT_GATE = 500 — Gate 订单簿档位上限
  ORDERBOOK_LIMIT_BITGET = 150 — Bitget 订单簿档位上限（API 最大 150）
  HTTP_TIMEOUT = 30.0        — HTTP 超时（秒）

  GATE_SYMBOLS — Gate 交易对 id（currency_pair）
  BITGET_SYMBOLS — Bitget 交易对 symbol

调用频率:
  按需手动运行；盘口变化快，不宜长时间循环（建议单次快照）。

依赖:
  Python 3.9+，httpx（pip install httpx）
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

try:
    import httpx
except ImportError:
    print("请先安装: pip install httpx")
    sys.exit(1)

DEPTH_PCT = 0.02
MARKET_BUY_USDT = 10000.0
ORDERBOOK_LIMIT_GATE = 500
ORDERBOOK_LIMIT_BITGET = 150
HTTP_TIMEOUT = 30.0

GATE_SYMBOLS = {
    "AAPLx": "AAPLX_USDT",
    "NVDAx": "NVDAX_USDT",
    "TSLAx": "TSLAX_USDT",
}

BITGET_SYMBOLS = {
    "AAPLON": "AAPLONUSDT",
    "NVDAON": "NVDAONUSDT",
    "TSLAON": "TSLAONUSDT",
}

GATE_ORDERBOOK_URL = "https://api.gateio.ws/api/v4/spot/order_book"
BITGET_ORDERBOOK_URL = "https://api.bitget.com/api/v2/spot/market/orderbook"


@dataclass
class BookSide:
    price: float
    qty_base: float

    @property
    def notional_usdt(self) -> float:
        return self.price * self.qty_base


@dataclass
class LiquidityMetrics:
    exchange: str
    label: str
    symbol: str
    best_bid: float
    best_ask: float
    mid: float
    spread_ratio: float  # (ask-bid)/mid，无量纲比例
    bid_depth_2pct_usdt: float
    ask_depth_2pct_usdt: float
    depth_2pct_total_usdt: float
    market_buy_usdt: float
    market_buy_vwap: Optional[float]
    market_buy_slippage_ratio: Optional[float]  # (vwap-mid)/mid
    market_buy_filled_usdt: float
    market_buy_filled_base: float
    book_warning: Optional[str] = None


def _parse_levels(raw: Sequence[Sequence]) -> List[BookSide]:
    out: List[BookSide] = []
    for row in raw:
        if not row or len(row) < 2:
            continue
        out.append(BookSide(price=float(row[0]), qty_base=float(row[1])))
    return out


def _mid_and_spread(bids: List[BookSide], asks: List[BookSide]) -> Tuple[float, float, float, float]:
    if not bids or not asks:
        raise ValueError("订单簿缺少买一或卖一")
    best_bid = bids[0].price
    best_ask = asks[0].price
    mid = (best_bid + best_ask) / 2.0
    spread_ratio = (best_ask - best_bid) / mid if mid > 0 else 0.0
    return best_bid, best_ask, mid, spread_ratio


def _depth_within_pct(levels: List[BookSide], mid: float, pct: float, side: str) -> float:
    """累计在 mid±pct 范围内的 USDT 名义深度。"""
    if side == "bid":
        floor_price = mid * (1.0 - pct)
        total = 0.0
        for lv in levels:
            if lv.price < floor_price:
                break
            total += lv.notional_usdt
        return total
    # ask
    ceil_price = mid * (1.0 + pct)
    total = 0.0
    for lv in levels:
        if lv.price > ceil_price:
            break
        total += lv.notional_usdt
    return total


def _simulate_market_buy_usdt(asks: List[BookSide], mid: float, quote_budget: float) -> Tuple[
    float, float, Optional[float], Optional[float], Optional[str]
]:
    """
    市价买入：按卖盘从低到高吃单，直到花完 quote_budget USDT。
    返回 (filled_quote, filled_base, vwap, slippage_ratio, warning)。
    """
    remaining = quote_budget
    filled_quote = 0.0
    filled_base = 0.0
    warning = None
    for lv in asks:
        if remaining <= 0:
            break
        level_quote = lv.notional_usdt
        take_quote = min(remaining, level_quote)
        take_base = take_quote / lv.price if lv.price > 0 else 0.0
        filled_quote += take_quote
        filled_base += take_base
        remaining -= take_quote
    if remaining > 1e-6:
        warning = "卖盘深度不足，仅成交 %.2f / %.2f USDT" % (filled_quote, quote_budget)
    if filled_base <= 0:
        return filled_quote, filled_base, None, None, warning or "无法成交"
    vwap = filled_quote / filled_base
    slippage_ratio = (vwap - mid) / mid if mid > 0 else None
    return filled_quote, filled_base, vwap, slippage_ratio, warning


def _fetch_gate_book(client: httpx.Client, pair: str) -> Tuple[List[BookSide], List[BookSide]]:
    r = client.get(
        GATE_ORDERBOOK_URL,
        params={"currency_pair": pair, "limit": ORDERBOOK_LIMIT_GATE},
    )
    r.raise_for_status()
    data = r.json()
    bids = _parse_levels(data.get("bids") or [])
    asks = _parse_levels(data.get("asks") or [])
    return bids, asks


def _fetch_bitget_book(client: httpx.Client, symbol: str) -> Tuple[List[BookSide], List[BookSide]]:
    r = client.get(
        BITGET_ORDERBOOK_URL,
        params={"symbol": symbol, "type": "step0", "limit": str(ORDERBOOK_LIMIT_BITGET)},
    )
    r.raise_for_status()
    body = r.json()
    if str(body.get("code", "00000")) not in ("00000", "0"):
        raise RuntimeError("Bitget orderbook: %s" % body)
    data = body.get("data") or {}
    bids = _parse_levels(data.get("bids") or [])
    asks = _parse_levels(data.get("asks") or [])
    return bids, asks


def _analyze(
    exchange: str,
    label: str,
    symbol: str,
    bids: List[BookSide],
    asks: List[BookSide],
) -> LiquidityMetrics:
    best_bid, best_ask, mid, spread_ratio = _mid_and_spread(bids, asks)
    bid_d = _depth_within_pct(bids, mid, DEPTH_PCT, "bid")
    ask_d = _depth_within_pct(asks, mid, DEPTH_PCT, "ask")
    filled_q, filled_b, vwap, slip_ratio, warn = _simulate_market_buy_usdt(
        asks, mid, MARKET_BUY_USDT
    )
    return LiquidityMetrics(
        exchange=exchange,
        label=label,
        symbol=symbol,
        best_bid=best_bid,
        best_ask=best_ask,
        mid=mid,
        spread_ratio=spread_ratio,
        bid_depth_2pct_usdt=bid_d,
        ask_depth_2pct_usdt=ask_d,
        depth_2pct_total_usdt=bid_d + ask_d,
        market_buy_usdt=MARKET_BUY_USDT,
        market_buy_vwap=vwap,
        market_buy_slippage_ratio=slip_ratio,
        market_buy_filled_usdt=filled_q,
        market_buy_filled_base=filled_b,
        book_warning=warn,
    )


def _print_metrics(m: LiquidityMetrics) -> None:
    print("")
    print("[%s] %s  symbol=%s" % (m.exchange, m.label, m.symbol))
    print("  买一/卖一/中间价: %.4f / %.4f / %.4f" % (m.best_bid, m.best_ask, m.mid))
    print("  盘口价差比例: %.6f  (相对中间价 (ask-bid)/mid)" % m.spread_ratio)
    print(
        "  2%%深度(USDT):  bid=%.2f  ask=%.2f  total=%.2f"
        % (m.bid_depth_2pct_usdt, m.ask_depth_2pct_usdt, m.depth_2pct_total_usdt)
    )
    if m.market_buy_vwap is not None:
        slip = m.market_buy_slippage_ratio or 0.0
        print(
            "  市价买入 %.0f USDT: VWAP=%.4f  滑点比例=%.6f  (相对中间价 (vwap-mid)/mid)  "
            "成交=%.2f USDT / %.6f base"
            % (
                m.market_buy_usdt,
                m.market_buy_vwap,
                slip,
                m.market_buy_filled_usdt,
                m.market_buy_filled_base,
            )
        )
    else:
        print("  市价买入 %.0f USDT: 无法估算滑点" % m.market_buy_usdt)
    if m.book_warning:
        print("  注意: %s" % m.book_warning)


def run() -> List[LiquidityMetrics]:
    results: List[LiquidityMetrics] = []
    print("Gate / Bitget 代币化股票现货流动性快照")
    print(
        "深度带宽=±%.0f%%  市价买入=%.0f USDT"
        % (DEPTH_PCT * 100, MARKET_BUY_USDT)
    )
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        print("\n--- Gate 现货 ---")
        for label, pair in GATE_SYMBOLS.items():
            try:
                bids, asks = _fetch_gate_book(client, pair)
                m = _analyze("Gate", label, pair, bids, asks)
                results.append(m)
                _print_metrics(m)
            except Exception as exc:  # noqa: BLE001
                print("\n[Gate] %s  ERROR: %s" % (label, exc))

        print("\n--- Bitget 现货 ---")
        for label, sym in BITGET_SYMBOLS.items():
            try:
                bids, asks = _fetch_bitget_book(client, sym)
                m = _analyze("Bitget", label, sym, bids, asks)
                results.append(m)
                _print_metrics(m)
            except Exception as exc:  # noqa: BLE001
                print("\n[Bitget] %s  ERROR: %s" % (label, exc))

    print("\n完成，共 %d 个标的。" % len(results))
    return results


if __name__ == "__main__":
    run()
