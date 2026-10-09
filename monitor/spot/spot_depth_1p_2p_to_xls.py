#!/usr/bin/env python3
# coding: utf-8
import argparse
import asyncio
import datetime
import os
import sys
from typing import Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from config.infor import SYMBOLS_PAIR, spot_account  # noqa: E402
from exchange.restful_api.abc_spot import AApi  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计现货交易对1%%/2%%深度USDT与挡位，并导出xls"
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出xls文件路径，默认当前目录自动生成文件名",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="逗号分隔交易对，如 BTC-USDT,ETH-USDT；不传则使用 config.infor.SYMBOLS_PAIR",
    )
    return parser.parse_args()


def get_symbols(symbols_arg: str) -> List[str]:
    if symbols_arg.strip():
        return [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
    return sorted(set(SYMBOLS_PAIR))


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def calc_side_depth(levels: List, threshold: float, side: str) -> Tuple[float, int]:
    total_usdt = 0.0
    level_count = 0
    for lv in levels:
        if not isinstance(lv, (list, tuple)) or len(lv) < 2:
            continue
        price = _safe_float(lv[0])
        amount = _safe_float(lv[1])
        if price <= 0 or amount <= 0:
            continue
        if side == "buy":
            if price < threshold:
                continue
        else:
            if price > threshold:
                continue
        total_usdt += price * amount
        level_count += 1
    return total_usdt, level_count


def calc_depth_metrics(depth_result: Dict) -> Dict:
    bids = depth_result.get("bids", [])
    asks = depth_result.get("asks", [])
    if not bids or not asks:
        raise ValueError("盘口为空")

    bid1 = _safe_float(bids[0][0]) if isinstance(bids[0], (list, tuple)) and len(bids[0]) >= 1 else 0.0
    ask1 = _safe_float(asks[0][0]) if isinstance(asks[0], (list, tuple)) and len(asks[0]) >= 1 else 0.0
    if bid1 <= 0 or ask1 <= 0:
        raise ValueError("买一或卖一价格异常")

    mid = (bid1 + ask1) / 2.0
    if mid <= 0:
        raise ValueError("中间价异常")

    buy_thr_1p = mid * 0.99
    sell_thr_1p = mid * 1.01
    buy_thr_2p = mid * 0.98
    sell_thr_2p = mid * 1.02

    buy_usdt_1p, buy_levels_1p = calc_side_depth(bids, buy_thr_1p, side="buy")
    sell_usdt_1p, sell_levels_1p = calc_side_depth(asks, sell_thr_1p, side="sell")
    buy_usdt_2p, buy_levels_2p = calc_side_depth(bids, buy_thr_2p, side="buy")
    sell_usdt_2p, sell_levels_2p = calc_side_depth(asks, sell_thr_2p, side="sell")

    return {
        "buy_usdt_1p": round(buy_usdt_1p, 4),
        "buy_levels_1p": buy_levels_1p,
        "sell_usdt_1p": round(sell_usdt_1p, 4),
        "sell_levels_1p": sell_levels_1p,
        "buy_usdt_2p": round(buy_usdt_2p, 4),
        "buy_levels_2p": buy_levels_2p,
        "sell_usdt_2p": round(sell_usdt_2p, 4),
        "sell_levels_2p": sell_levels_2p,
    }


def create_api(token: str, secret_key: str) -> AApi:
    # abc_spot.py 在 request() 内会关闭 session，复用同一实例可能触发后续请求异常
    return AApi(token=token, secret_key=secret_key)


async def fetch_one_symbol(token: str, secret_key: str, symbol: str) -> Dict:
    row = {
        "symbol": symbol,
        "buy_usdt_1p": 0.0,
        "buy_levels_1p": 0,
        "sell_usdt_1p": 0.0,
        "sell_levels_1p": 0,
        "buy_usdt_2p": 0.0,
        "buy_levels_2p": 0,
        "sell_usdt_2p": 0.0,
        "sell_levels_2p": 0,
        "snapshot_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ok",
    }
    for _ in range(2):
        try:
            api = create_api(token, secret_key)
            data = await api.depth(symbol)
            if not isinstance(data, dict):
                raise ValueError("接口返回非字典")
            if data.get("errno") != 0:
                raise ValueError("errno=%s, errmsg=%s" % (data.get("errno"), data.get("errmsg")))
            result = data.get("result", {})
            if not isinstance(result, dict):
                raise ValueError("result结构异常")
            row.update(calc_depth_metrics(result))
            return row
        except Exception as e:
            row["status"] = str(e)
    return row


def build_output_path(output_arg: str) -> str:
    if output_arg.strip():
        return output_arg
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(os.getcwd(), "spot_depth_1p_2p_%s.xls" % ts)


def export_xls(rows: List[Dict], output_path: str) -> None:
    try:
        import xlwt
    except Exception as e:
        raise RuntimeError("缺少xlwt依赖，请先安装: pip install xlwt") from e

    headers = [
        "symbol",
        "buy_usdt_1p", "buy_levels_1p", "sell_usdt_1p", "sell_levels_1p",
        "buy_usdt_2p", "buy_levels_2p", "sell_usdt_2p", "sell_levels_2p",
        "snapshot_time", "status",
    ]

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("depth_1p_2p")
    for col, h in enumerate(headers):
        ws.write(0, col, h)

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, h in enumerate(headers):
            ws.write(r_idx, c_idx, row.get(h, ""))

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    wb.save(output_path)


async def run() -> int:
    args = parse_args()
    symbols = get_symbols(args.symbols)
    if not symbols:
        print("没有可处理的交易对")
        return 1

    first_acc = next(iter(spot_account.values()), None)
    if not first_acc:
        print("spot_account为空，无法初始化AApi")
        return 1

    token = first_acc["apikey"]["token"]
    secret_key = first_acc["apikey"]["sk"]
    rows = []
    ok_count = 0
    fail_count = 0

    for symbol in symbols:
        row = await fetch_one_symbol(token, secret_key, symbol)
        rows.append(row)
        if row["status"] == "ok":
            ok_count += 1
        else:
            fail_count += 1

    output_path = build_output_path(args.output)
    export_xls(rows, output_path)
    print("总数: %d, 成功: %d, 失败: %d" % (len(symbols), ok_count, fail_count))
    print("输出文件: %s" % output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

