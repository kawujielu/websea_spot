"""查询指定日期范围内，现货成交库所有用户已实现盈亏总和（单位：USDT）。

口径:
- 库: exchange.real_deal（与 mongdb_spot_deal.py 同款现货 Mongo）
- 仅统计 quote 为 USDT 的交易对（symbol 以 -USDT 结尾）
- 剔除 MH-USDT、WBS-USDT
- type = fromUser 方向；toUser 为反向
- 做市账户 11–17 的用户侧不计入
- 现货无 ProfitLoss：按「用户+交易对」均价持仓，平仓盈亏 = (成交价-均价)*数量（USDT）
- 手续费折算成 USDT 后再扣（买：fee×price；卖：fee 已是报价币）
- 按交易对汇总盈亏
- 时间按北京时间闭区间，精确到秒

运行:
  py mongdb_realized_pnl_sum.py
依赖: pip install motor
"""
from __future__ import annotations

import asyncio
import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

import motor.motor_asyncio

# ========== 配置 ==========
# 与 mongdb_spot_deal.py 同款现货可读库
MONGO_URI = "mongodb://spot-ro:PcwDn46F24MHGjRa@10.60.99.86:27018/"
MONGO_SERVER_SELECTION_TIMEOUT_MS = 5000
BEGIN_DATE = "2026-05-07 16:11:00"  # 北京时间 YYYY-MM-DD HH:MM:SS
END_DATE = "2026-09-22 21:45:58"
MM_IDS = [11, 12, 13, 14, 15, 16, 17]  # 做市账户，其盈亏不计入
EXCLUDE_SYMBOLS = {"MH-USDT", "WBS-USDT"}  # 剔除的交易对
# ==========================

_BJT = datetime.timezone(datetime.timedelta(hours=8))
_MM = {str(x) for x in MM_IDS}


def _bjt_range_to_ts(begin: str, end: str):
    """北京时间闭区间 [begin, end]，精确到秒 → unix 秒。"""
    lo = datetime.datetime.strptime(begin, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BJT)
    hi = datetime.datetime.strptime(end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BJT)
    return int(lo.timestamp()), int(hi.timestamp())


def _fee_usdt(side: str, fee: float, price: float) -> float:
    """手续费折成 USDT。买扣标的币 → fee*price；卖扣报价币 → fee。"""
    if side == "buy":
        return fee * price
    return fee


def _legs(deal: dict) -> List[Tuple[str, str, float, float, float]]:
    """返回 [(userid, side, amount, price, fee_usdt), ...]；side 为 buy/sell。"""
    from_u = str(deal.get("fromUser") or "")
    to_u = str(deal.get("toUser") or "")
    deal_type = str(deal.get("type") or "").lower()
    price = float(deal.get("price") or 0)
    amount = float(deal.get("amount") or 0)
    if amount <= 0 or price <= 0 or deal_type not in ("buy", "sell"):
        return []
    to_side = "sell" if deal_type == "buy" else "buy"
    from_fee = float(deal.get("fromFee") or 0)
    to_fee = float(deal.get("toFee") or 0)
    return [
        (from_u, deal_type, amount, price, _fee_usdt(deal_type, from_fee, price)),
        (to_u, to_side, amount, price, _fee_usdt(to_side, to_fee, price)),
    ]


def _apply_fill(
    pos: float,
    avg: float,
    side: str,
    qty: float,
    price: float,
) -> Tuple[float, float, float]:
    """均价持仓：返回 (new_pos, new_avg, realized_pnl_usdt)。数量×价差即为报价币 USDT。"""
    realized = 0.0
    if side == "buy":
        if pos < -1e-12:
            # 回补空头
            cover = min(qty, -pos)
            realized += (avg - price) * cover
            pos += cover
            qty -= cover
            if abs(pos) < 1e-12:
                pos, avg = 0.0, 0.0
            if qty > 1e-12:
                pos = qty
                avg = price
        else:
            new_pos = pos + qty
            avg = (avg * pos + price * qty) / new_pos if new_pos else 0.0
            pos = new_pos
    else:  # sell
        if pos > 1e-12:
            close = min(qty, pos)
            realized += (price - avg) * close
            pos -= close
            qty -= close
            if abs(pos) < 1e-12:
                pos, avg = 0.0, 0.0
            if qty > 1e-12:
                pos = -qty
                avg = price
        else:
            new_pos = pos - qty  # 更空或开空
            if pos < -1e-12:
                avg = (avg * (-pos) + price * qty) / (-new_pos) if new_pos else 0.0
            else:
                avg = price
            pos = new_pos
    return pos, avg, realized


async def sum_realized_pnl(begin_date: str, end_date: str) -> dict:
    ts_min, ts_max = _bjt_range_to_ts(begin_date, end_date)
    client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGO_URI,
        serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    col = client.exchange.real_deal
    try:
        await client.admin.command("ping")
    except Exception as e:
        raise SystemExit(
            f"无法连接现货 Mongo: {MONGO_URI}\n原因: {e}\n"
            "该地址为内网库，请在可访问 10.60.99.86:27018 的机器上运行，"
            "或先做 SSH 隧道后把 MONGO_URI 改成 127.0.0.1。"
        ) from e

    # (uid, symbol) -> (pos, avg)
    book: Dict[Tuple[str, str], Tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    by_symbol: Dict[str, float] = defaultdict(float)
    by_symbol_n: Dict[str, int] = defaultdict(int)
    total_pnl = 0.0
    leg_count = 0

    cursor = col.aggregate(
        [
            {"$match": {"ts": {"$gte": ts_min, "$lte": ts_max}}},
            {"$sort": {"ts": 1}},
        ],
        allowDiskUse=True,
    )
    async for deal in cursor:
        symbol = str(deal.get("symbol") or "")
        if not symbol.endswith("-USDT") or symbol.upper() in EXCLUDE_SYMBOLS:
            continue
        for uid, side, amount, price, fee_usdt in _legs(deal):
            if not uid or uid in ("0", "None") or uid in _MM:
                continue
            leg_count += 1
            key = (uid, symbol)
            pos, avg = book[key]
            pos, avg, realized = _apply_fill(pos, avg, side, amount, price)
            book[key] = (pos, avg)
            # 价差盈亏已是 USDT；手续费折成 USDT 后扣除
            realized -= fee_usdt
            if abs(realized) < 1e-12:
                continue
            total_pnl += realized
            by_symbol[symbol] += realized
            by_symbol_n[symbol] += 1

    symbol_rows = sorted(
        (
            {"_id": s, "pnl": p, "leg_count": by_symbol_n[s]}
            for s, p in by_symbol.items()
        ),
        key=lambda x: x["pnl"],
        reverse=True,
    )
    return {
        "leg_count": leg_count,
        "total_pnl": total_pnl,
        "by_symbol": symbol_rows,
    }


async def main():
    print(
        f"查询 real_deal 已实现盈亏(USDT) 区间={BEGIN_DATE}~{END_DATE}(BJT) "
        f"排除做市={MM_IDS} 剔除={sorted(EXCLUDE_SYMBOLS)} 仅*-USDT"
    )
    r = await sum_realized_pnl(BEGIN_DATE, END_DATE)
    print(f"用户侧笔数={r['leg_count']} 已实现盈亏总和={r['total_pnl']:.4f} USDT")

    print("\n—— 按交易对盈亏(USDT) ——")
    print(f"{'交易对':<16} {'盈亏USDT':>14} {'计入笔数':>10}")
    for row in r["by_symbol"]:
        print(f"{str(row['_id']):<16} {float(row['pnl']):>14.4f} {int(row['leg_count']):>10}")


if __name__ == "__main__":
    asyncio.run(main())

