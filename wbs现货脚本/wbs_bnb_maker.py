#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WBS 现货铺单：mid 跟随 Binance BNB 相对涨跌并按 bnb_amplify 放大（默认 5x）；
买卖各挂 order_count 单，单边总金额 order_amount USDT，随机拆份后按从小到大分配到近->远档。

方案 B：
  - 启动时先全撤该交易对未完成挂单，再铺单
  - 公共 oapi 无 upOrder：价变才撤挂；use_up_order 可开改价
  - 撤挂按档位每 10 档一批：先撤远后撤近，再挂回
  - 避免自成交（买价始终 < 卖一目标价，卖价始终 > 买一目标价）
  - 每 5min 热加载同目录 yaml

用法：
  pip3 install requests pyyaml
  # 编辑 wbs_bnb_maker.yaml 填写 token/secret_key，dry_run: false
  python3 wbs_bnb_maker.py
  python3 wbs_bnb_maker.py --config wbs_bnb_maker.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time
import traceback
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "wbs_bnb_maker.yaml")


def digit_to_string(d: float, prec: Optional[int] = None) -> str:
    """按精度格式化为字符串，避免 float 二进制误差（如 634.7 -> 634.7000000000000455）。"""
    if prec is not None:
        prec = int(prec)
        if prec <= 0:
            return str(int(round(float(d))))
        s = "{:.{p}f}".format(float(d), p=prec)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s if s else "0"
    s = ("{:.16f}".format(float(d))).rstrip("0").rstrip(".")
    return s if s else "0"


def round_px(price: float, prec: int) -> float:
    return round(float(price), prec) if prec > 0 else round(float(price))


def tick_size(prec: int) -> float:
    return 10 ** (-prec) if prec > 0 else 1.0


# ---------------------------------------------------------------------------
# API（签名逻辑对齐 spot_market_maker/abcapi_plus.py）
# ---------------------------------------------------------------------------
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
            "User-Agent": "wbs_bnb_maker/1.0",
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
        # 部分不存在的路径会 HTTP 404 或 JSON errno=404，统一交给调用方处理回退
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

    def precision(self, symbol: str) -> Dict[str, Any]:
        res = self.request("GET", "/openApi/market/precision")
        if res.get("errno") != 0:
            raise RuntimeError("precision 失败: {}".format(res))
        result = res.get("result") or {}
        if symbol in result:
            return result[symbol]
        # 部分环境 result 是 list
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and item.get("symbol") == symbol:
                    return item
        raise RuntimeError("精度中无交易对 {}".format(symbol))

    def depth(self, symbol: str) -> dict:
        res = self.request("GET", "/openApi/market/depth", {"symbol": symbol})
        if res.get("errno") != 0:
            raise RuntimeError("depth 失败: {}".format(res))
        return res.get("result") or {}

    def current_list(self, symbol: str) -> List[dict]:
        # 优先新版未完成委托，失败再回退旧版
        res = self.request("GET", "/v1/spot/orders/open", {"symbol": symbol, "limit": 100})
        if res.get("errno") == 404:
            res = self.request("GET", "/openApi/entrust/currentList", {"symbol": symbol})
        if res.get("errno") != 0:
            return []
        result = res.get("result") or []
        if isinstance(result, dict):
            result = result.get("list") or result.get("orders") or result.get("data") or []
        return list(result) if isinstance(result, list) else []

    def add(self, symbol: str, order_type: str, amount: str, price: str) -> dict:
        """单笔下单。oapi 公共接口无 batchAdd，需逐笔调用。"""
        # 优先新版路径，失败再回退旧版（过渡期并存）
        payload = {
            "symbol": symbol,
            "type": order_type,
            "amount": amount,
            "price": price,
        }
        res = self.request("POST", "/v1/spot/order/create", payload)
        if res.get("errno") == 404:
            res = self.request("POST", "/openApi/entrust/add", payload)
        return res

    def batch_add(self, orders: List[dict]) -> dict:
        """
        兼容原 batchAdd 调用方。
        公共 oapi 无 /openApi/entrust/batchAdd（errno 404），改为逐笔 add。
        支持订单中带 _side/_level/_usdt 仅用于日志，不会提交给交易所。
        """
        success: List[dict] = []
        failed: List[dict] = []
        total = len(orders)
        for i, o in enumerate(orders, 1):
            side = o.get("_side") or o.get("type")
            lv = o.get("_level", "-")
            usdt = o.get("_usdt")
            usdt_s = round(float(usdt), 6) if usdt is not None else "-"
            tag = "[{}/{}]".format(i, total)
            try:
                res = self.add(o["symbol"], o["type"], o["amount"], o["price"])
            except Exception as e:
                failed.append({"order": o, "error": str(e)})
                print(
                    "[PLACE-FAIL] {} {} lv{} {} price={} amount={} usdt~{} err={}".format(
                        tag, o.get("symbol"), lv, side, o.get("price"), o.get("amount"), usdt_s, e
                    )
                )
                continue
            if res.get("errno") == 0:
                result = res.get("result") or {}
                sn = ""
                if isinstance(result, dict):
                    sn = str(result.get("order_sn") or result.get("id") or "")
                success.append({"order_sn": sn, "order": o, "raw": res})
                print(
                    "[PLACE-OK] {} {} lv{} {} price={} amount={} usdt~{} sn={}".format(
                        tag, o.get("symbol"), lv, side, o.get("price"), o.get("amount"), usdt_s, sn
                    )
                )
            else:
                failed.append({"order": o, "raw": res})
                print(
                    "[PLACE-FAIL] {} {} lv{} {} price={} amount={} usdt~{} errno={} errmsg={}".format(
                        tag,
                        o.get("symbol"),
                        lv,
                        side,
                        o.get("price"),
                        o.get("amount"),
                        usdt_s,
                        res.get("errno"),
                        res.get("errmsg"),
                    )
                )
        errno = 0 if success and not failed else (0 if success else -1)
        print(
            "[PLACE-SUM] ok={} fail={} total={}".format(
                len(success), len(failed), total
            )
        )
        return {
            "errno": errno,
            "errmsg": "success" if not failed else "partial_or_fail",
            "result": {"success": success, "failed": failed},
        }

    def up_order(self, order_sn: str, symbol: str, amount: str, price: str) -> dict:
        # upOrder 多为做市内网接口；公共 oapi 可能 404，调用方会走撤挂兜底
        return self.request(
            "POST",
            "/openApi/entrust/upOrder",
            {
                "order_sn": order_sn,
                "symbol": symbol,
                "amount": amount,
                "price": price,
            },
        )

    def cancel(self, order_ids: List[str], symbol: str = "") -> dict:
        data = {"order_ids": ",".join(order_ids)}
        if symbol:
            data["symbol"] = symbol
        res = self.request("POST", "/v1/spot/order/cancel", data)
        if res.get("errno") == 404:
            res = self.request("POST", "/openApi/entrust/cancel", data)
        return res


def fetch_binance_price(host: str, symbol: str) -> float:
    url = host.rstrip("/") + "/api/v3/ticker/price"
    r = requests.get(url, params={"symbol": symbol}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return float(data["price"])


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ValueError("yaml 根节点必须是 map")
    return cfg


def cfg_get(cfg: dict, key: str, default=None):
    v = cfg.get(key, default)
    return default if v is None or v == "" else v


# ---------------------------------------------------------------------------
# 价格阶梯
# ---------------------------------------------------------------------------
def level_gap_ticks(next_level: int) -> int:
    """下一档相对当前档的价差（价格最小单位个数）。"""
    if next_level <= 10:
        return 1
    if next_level < 30:
        return random.randint(2, 5)
    return random.randint(5, 10)


def build_ladder(
    mid: float, order_count: int, price_ratio: float, price_prec: int
) -> Tuple[List[float], List[float]]:
    tick = tick_size(price_prec)
    buy1 = round_px(mid * (1.0 - price_ratio), price_prec)
    sell1 = round_px(mid * (1.0 + price_ratio), price_prec)
    # 避免自成交：买卖一至少隔 1 tick
    if sell1 <= buy1:
        buy1 = round_px(mid - tick, price_prec)
        sell1 = round_px(mid + tick, price_prec)
        if sell1 <= buy1:
            sell1 = round_px(buy1 + tick, price_prec)

    buys = [buy1]
    sells = [sell1]
    bp, sp = buy1, sell1
    for lv in range(1, order_count):
        gap = level_gap_ticks(lv + 1)
        bp = round_px(bp - gap * tick, price_prec)
        sp = round_px(sp + gap * tick, price_prec)
        if bp <= 0:
            bp = tick
        buys.append(bp)
        sells.append(sp)
    return buys, sells


def notional_to_amount(notional: float, price: float, amount_prec: int) -> float:
    if price <= 0:
        return 0.0
    # 用字符串进 Decimal，避免 float 除法/四舍五入残留
    amt = Decimal(str(notional)) / Decimal(str(price))
    if amount_prec > 0:
        q = Decimal(10) ** -int(amount_prec)
        amt = amt.quantize(q, rounding=ROUND_DOWN)
    else:
        amt = amt.to_integral_value(rounding=ROUND_DOWN)
    return float(amt)


def split_total_usdt(total: float, order_count: int) -> List[float]:
    """把总 USDT 随机拆成 order_count 份，按从小到大排序（近档小、远档大）。"""
    n = max(1, int(order_count))
    total = float(total)
    if n == 1:
        return [total]
    weights = sorted(random.random() for _ in range(n))
    s = sum(weights) or 1.0
    parts = [total * w / s for w in weights]
    # 尾差归到最后一档，保证加总精确
    parts[-1] = total - sum(parts[:-1])
    return parts


# ---------------------------------------------------------------------------
# 策略
# ---------------------------------------------------------------------------
class WbsBnbMaker:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.cfg: dict = {}
        self.api: Optional[SpotApi] = None
        self.mid: Optional[float] = None
        self.last_bnb: Optional[float] = None
        self.price_prec = 8
        self.amount_prec = 6
        # tracked[(side, level)] = order_sn   side: buy/sell, level: 0..order_count-1
        self.tracked: Dict[Tuple[str, int], str] = {}
        # 当前挂单价；公共 oapi 无改价接口时，仅价格变化才撤挂
        self.tracked_price: Dict[Tuple[str, int], float] = {}
        # 公共 oapi 无 /openApi/entrust/upOrder；默认关闭，yaml 可开
        self.use_up_order = False
        self.buy_usdt: List[float] = []
        self.sell_usdt: List[float] = []
        self.last_yaml_reload = 0.0
        self._apply_config(load_config(config_path), first=True)

    def rebuild_usdt_splits(self) -> None:
        self.buy_usdt = split_total_usdt(self.order_amount, self.order_count)
        self.sell_usdt = split_total_usdt(self.order_amount, self.order_count)
        print(
            "[USDT] 单边总额={} 买档份数(小->大)={}..{} 卖档份数={}..{}".format(
                self.order_amount,
                round(self.buy_usdt[0], 6),
                round(self.buy_usdt[-1], 6),
                round(self.sell_usdt[0], 6),
                round(self.sell_usdt[-1], 6),
            )
        )

    def _apply_config(self, cfg: dict, first: bool = False) -> None:
        old_count = getattr(self, "order_count", None)
        old_amount = getattr(self, "order_amount", None)
        self.cfg = cfg
        host = str(cfg_get(cfg, "host", "https://oapi.websea.com"))
        token = str(cfg_get(cfg, "token", "") or "")
        secret = str(cfg_get(cfg, "secret_key", "") or "")
        self.symbol = str(cfg_get(cfg, "symbol", "WBS-USDT"))
        self.binance_host = str(cfg_get(cfg, "binance_host", "https://api.binance.com"))
        self.ref_symbol = str(cfg_get(cfg, "ref_symbol", "BNBUSDT"))
        self.order_count = max(1, int(cfg_get(cfg, "order_count", 50)))
        self.order_amount = float(cfg_get(cfg, "order_amount", 10))
        self.price_ratio = float(cfg_get(cfg, "price_ratio", 0.0002))
        # BNB 相对涨跌对 mid 的放大倍数：BNB 涨 1% → mid 涨 amplify%
        self.bnb_amplify = float(cfg_get(cfg, "bnb_amplify", 5))
        self.loop_interval = float(cfg_get(cfg, "loop_interval_sec", 3))
        self.yaml_reload_sec = float(cfg_get(cfg, "yaml_reload_sec", 300))
        self.dry_run = bool(cfg_get(cfg, "dry_run", True))
        # 公共 oapi 无改价接口；仅做市内网才开 use_up_order: true
        self.use_up_order = bool(cfg_get(cfg, "use_up_order", False))
        self.initial_mid = cfg_get(cfg, "initial_mid", None)
        if self.initial_mid is not None:
            self.initial_mid = float(self.initial_mid)

        pp = cfg_get(cfg, "price_precision", None)
        ap = cfg_get(cfg, "amount_precision", None)
        if pp is not None:
            self.price_prec = int(pp)
        if ap is not None:
            self.amount_prec = int(ap)

        if token and secret:
            self.api = SpotApi(host, token, secret)
        else:
            self.api = None
            if first:
                print("[WARN] token/secret_key 为空，强制 dry_run")
            self.dry_run = True

        # order_count 变小：丢掉远处跟踪（实际撤单在 sync 时处理）
        drop = [k for k in self.tracked if k[1] >= self.order_count]
        for k in drop:
            self.tracked.pop(k, None)
            self.tracked_price.pop(k, None)

        if (
            first
            or old_count != self.order_count
            or old_amount != self.order_amount
            or len(self.buy_usdt) != self.order_count
        ):
            self.rebuild_usdt_splits()

        print(
            "[CFG] symbol={} order_count={} order_amount(total/side)={} ratio={} bnb_amplify={}x interval={}s dry_run={}".format(
                self.symbol,
                self.order_count,
                self.order_amount,
                self.price_ratio,
                self.bnb_amplify,
                self.loop_interval,
                self.dry_run,
            )
        )

    def maybe_reload_yaml(self) -> None:
        now = time.time()
        if now - self.last_yaml_reload < self.yaml_reload_sec:
            return
        try:
            cfg = load_config(self.config_path)
            self._apply_config(cfg, first=False)
            self.last_yaml_reload = now
            print("[CFG] yaml 已热加载 {}".format(time.strftime("%H:%M:%S")))
        except Exception as e:
            print("[CFG] 热加载失败: {}".format(e))

    def ensure_precision(self) -> None:
        if cfg_get(self.cfg, "price_precision") is not None and cfg_get(
            self.cfg, "amount_precision"
        ) is not None:
            return
        if not self.api:
            return
        prec = self.api.precision(self.symbol)
        if cfg_get(self.cfg, "price_precision") is None:
            self.price_prec = int(prec.get("price", self.price_prec))
        if cfg_get(self.cfg, "amount_precision") is None:
            self.amount_prec = int(prec.get("amount", self.amount_prec))
        print("[PREC] price={} amount={}".format(self.price_prec, self.amount_prec))

    def init_mid(self) -> None:
        if self.initial_mid is not None and self.initial_mid > 0:
            self.mid = float(self.initial_mid)
            print("[MID] 使用 yaml initial_mid={}".format(self.mid))
            return
        if self.api:
            depth = self.api.depth(self.symbol)
            bids = depth.get("bids") or []
            asks = depth.get("asks") or []
            if bids and asks:
                bid1 = float(bids[0][0])
                ask1 = float(asks[0][0])
                self.mid = (bid1 + ask1) / 2.0
                print("[MID] 盘口中间价={}".format(self.mid))
                return
            print("[MID] 盘口为空，回退失败")
        raise RuntimeError("请在 yaml 填写 initial_mid，或配置有效 token 以读取盘口")

    def update_mid_from_bnb(self) -> None:
        bnb = fetch_binance_price(self.binance_host, self.ref_symbol)
        if self.last_bnb is None or self.mid is None:
            self.last_bnb = bnb
            print("[BNB] init {} mid={} amplify={}x".format(bnb, self.mid, self.bnb_amplify))
            return
        if self.last_bnb > 0:
            bnb_ratio = bnb / self.last_bnb
            if bnb_ratio != 1.0:
                # mid 按 BNB 相对涨跌 * amplify：1 + amplify * (bnb_ratio - 1)
                amp = float(self.bnb_amplify)
                mid_ratio = 1.0 + amp * (bnb_ratio - 1.0)
                # 极端行情保护：mid 不得 <= 0
                if mid_ratio <= 0:
                    print(
                        "[BNB] mid_ratio={:.8f}<=0 跳过本次跟随 bnb {} -> {}".format(
                            mid_ratio, self.last_bnb, bnb
                        )
                    )
                else:
                    old = self.mid
                    self.mid = old * mid_ratio
                    print(
                        "[BNB] {} -> {} bnb_chg={:+.6%} mid_chg={:+.6%} ({}x) mid {} -> {}".format(
                            self.last_bnb,
                            bnb,
                            bnb_ratio - 1.0,
                            mid_ratio - 1.0,
                            amp,
                            old,
                            self.mid,
                        )
                    )
        self.last_bnb = bnb

    def level_usdt(self, side: str, level: int) -> float:
        arr = self.buy_usdt if side == "buy" else self.sell_usdt
        if 0 <= level < len(arr):
            return arr[level]
        return self.order_amount / max(1, self.order_count)

    def make_order_payload(self, side: str, price: float, level: int) -> dict:
        usdt = self.level_usdt(side, level)
        amount = notional_to_amount(usdt, price, self.amount_prec)
        return {
            "symbol": self.symbol,
            "type": "buy-limit" if side == "buy" else "sell-limit",
            "amount": digit_to_string(amount, self.amount_prec),
            "price": digit_to_string(round_px(price, self.price_prec), self.price_prec),
            "_level": level,
            "_side": side,
            "_usdt": usdt,
        }

    def _print_orders(self, orders: List[dict], tag: str = "ORDER") -> None:
        for o in orders:
            print(
                "[{}] {} lv{} price={} amount={} usdt~{}".format(
                    tag,
                    o.get("_side") or o.get("type"),
                    o.get("_level", "-"),
                    o.get("price"),
                    o.get("amount"),
                    round(float(o.get("_usdt", 0)), 6),
                )
            )

    def place_batch(self, orders: List[dict]) -> List[str]:
        """返回成功 order_sn 列表（尽量按入参顺序）。"""
        if not orders:
            return []
        api_orders = [
            {
                "symbol": o["symbol"],
                "type": o["type"],
                "amount": o["amount"],
                "price": o["price"],
                "_level": o.get("_level"),
                "_side": o.get("_side"),
                "_usdt": o.get("_usdt"),
            }
            for o in orders
        ]
        if self.dry_run or not self.api:
            sns = ["DRY-{}-{}".format(int(time.time()), i) for i in range(len(api_orders))]
            for i, (o, sn) in enumerate(zip(orders, sns), 1):
                print(
                    "[DRY-PLACE] [{}/{}] {} lv{} {} price={} amount={} usdt~{} sn={}".format(
                        i,
                        len(orders),
                        o.get("symbol"),
                        o.get("_level", "-"),
                        o.get("_side") or o.get("type"),
                        o.get("price"),
                        o.get("amount"),
                        round(float(o.get("_usdt", 0) or 0), 6),
                        sn,
                    )
                )
            print("[PLACE-SUM] ok={} fail=0 total={} (dry_run)".format(len(sns), len(sns)))
            return sns
        res = self.api.batch_add(api_orders)
        result = res.get("result") or {}
        failed = []
        if isinstance(result, dict):
            failed = result.get("failed") or []
        if failed:
            print("[ERR] place 失败 {} 单".format(len(failed)))
        if res.get("errno") != 0 and not (
            isinstance(result, dict) and (result.get("success") or result.get("orders"))
        ):
            print("[ERR] place: {}".format(res))
            return []
        sns: List[str] = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    sn = item.get("order_sn") or item.get("id")
                    if sn:
                        sns.append(str(sn))
                elif item:
                    sns.append(str(item))
        elif isinstance(result, dict):
            success = result.get("success") or result.get("orders") or []
            for item in success:
                if isinstance(item, dict):
                    sn = item.get("order_sn") or item.get("id")
                    if sn:
                        sns.append(str(sn))
                elif item:
                    sns.append(str(item))
        if len(sns) != len(orders):
            print("[WARN] place 返回 sn 数 {} != 下单数 {}".format(len(sns), len(orders)))
        return sns

    def cancel_ids(self, order_sns: List[str]) -> None:
        order_sns = [x for x in order_sns if x and not str(x).startswith("DRY-")]
        if not order_sns:
            if self.dry_run:
                print("[DRY] cancel {}".format(len(order_sns)))
            return
        if self.dry_run or not self.api:
            print("[DRY] cancel {}".format(order_sns))
            return
        res = self.api.cancel(order_sns, symbol=self.symbol)
        if res.get("errno") != 0:
            print("[ERR] cancel: {}".format(res))

    @staticmethod
    def _order_sn_of(item: dict) -> str:
        if not isinstance(item, dict):
            return ""
        sn = item.get("order_sn") or item.get("id") or item.get("order_id") or ""
        return str(sn) if sn else ""

    def cancel_all_open(self) -> None:
        """启动时全撤该交易对未完成委托。"""
        self.tracked.clear()
        self.tracked_price.clear()
        if self.dry_run or not self.api:
            print("[DRY] cancel_all_open {}".format(self.symbol))
            return
        try:
            opens = self.api.current_list(self.symbol)
        except Exception as e:
            print("[ERR] 查询挂单失败: {}".format(e))
            return
        sns = []
        for item in opens:
            sn = self._order_sn_of(item)
            if sn:
                sns.append(sn)
        # 去重保序
        seen = set()
        uniq = []
        for sn in sns:
            if sn not in seen:
                seen.add(sn)
                uniq.append(sn)
        if not uniq:
            print("[BOOT] 无未完成挂单，跳过全撤")
            return
        print("[BOOT] 启动全撤 {} 单".format(len(uniq)))
        for start in range(0, len(uniq), 20):
            self.cancel_ids(uniq[start : start + 20])
            time.sleep(0.05)
        print("[BOOT] 全撤完成")

    def try_edit(self, order_sn: str, side: str, level: int, price: float) -> bool:
        if not self.use_up_order:
            return False
        usdt = self.level_usdt(side, level)
        amount = digit_to_string(
            notional_to_amount(usdt, price, self.amount_prec), self.amount_prec
        )
        price_s = digit_to_string(round_px(price, self.price_prec), self.price_prec)
        if self.dry_run or not self.api or str(order_sn).startswith("DRY-"):
            return True
        try:
            res = self.api.up_order(order_sn, self.symbol, amount, price_s)
            ok = res.get("errno") == 0
            if not ok:
                if res.get("errno") == 404:
                    self.use_up_order = False
                    print("[EDIT] upOrder 不可用(404)，之后改价走撤挂")
                else:
                    print(
                        "[EDIT-FAIL] {} {} {} -> {}".format(
                            side, order_sn, price_s, res
                        )
                    )
            return ok
        except Exception as e:
            print("[EDIT-FAIL] {} {} {}".format(side, order_sn, e))
            return False

    def _price_changed(self, key: Tuple[str, int], price: float) -> bool:
        old = self.tracked_price.get(key)
        if old is None:
            return True
        return round_px(old, self.price_prec) != round_px(price, self.price_prec)

    def bootstrap_orders(self, buys: List[float], sells: List[float]) -> None:
        # 先挂卖后挂买，降低自成交风险
        payloads = []
        keys: List[Tuple[str, int]] = []
        for i, p in enumerate(sells):
            payloads.append(self.make_order_payload("sell", p, i))
            keys.append(("sell", i))
        for i, p in enumerate(buys):
            payloads.append(self.make_order_payload("buy", p, i))
            keys.append(("buy", i))
        # 分批 batch，每批最多 20
        self.tracked.clear()
        self.tracked_price.clear()
        for start in range(0, len(payloads), 20):
            chunk = payloads[start : start + 20]
            chunk_keys = keys[start : start + 20]
            sns = self.place_batch(chunk)
            for k, sn, o in zip(chunk_keys, sns, chunk):
                self.tracked[k] = sn
                self.tracked_price[k] = float(o["price"])
            time.sleep(0.05)
        print("[BOOT] tracked={}".format(len(self.tracked)))

    def sync_orders(self, buys: List[float], sells: List[float]) -> None:
        """有 upOrder 则改价；否则仅价格变化时撤挂。按远->近每 10 档。"""
        tick = tick_size(self.price_prec)
        buy1_t, sell1_t = buys[0], sells[0]
        # 自成交保护：目标买价不得 >= 卖一，卖价不得 <= 买一
        buys = [min(p, round_px(sell1_t - tick, self.price_prec)) for p in buys]
        sells = [max(p, round_px(buy1_t + tick, self.price_prec)) for p in sells]

        targets = {("buy", i): buys[i] for i in range(len(buys))}
        targets.update({("sell", i): sells[i] for i in range(len(sells))})

        # 多余远处单先撤
        extra = [k for k in list(self.tracked) if k not in targets]
        if extra:
            # 远先撤
            extra.sort(key=lambda x: x[1], reverse=True)
            self.cancel_ids([self.tracked[k] for k in extra])
            for k in extra:
                self.tracked.pop(k, None)
                self.tracked_price.pop(k, None)

        need_replace: List[Tuple[str, int]] = []
        missing: List[Tuple[str, int]] = []

        for key, price in targets.items():
            sn = self.tracked.get(key)
            if not sn:
                missing.append(key)
                continue
            if not self._price_changed(key, price):
                continue
            side, level = key
            if self.use_up_order and self.try_edit(sn, side, level, price):
                self.tracked_price[key] = round_px(price, self.price_prec)
                continue
            need_replace.append(key)

        # 需撤挂 + 缺失：按档位远->近，每 10 档撤+挂
        todo = sorted(set(need_replace + missing), key=lambda x: x[1], reverse=True)
        if not todo:
            return

        for start in range(0, len(todo), 10):
            chunk = todo[start : start + 10]
            # 先撤远（chunk 已远->近）
            cancel_sns = []
            for k in chunk:
                sn = self.tracked.pop(k, None)
                self.tracked_price.pop(k, None)
                if sn:
                    cancel_sns.append(sn)
            if cancel_sns:
                self.cancel_ids(cancel_sns)
                time.sleep(0.05)

            # 同批内先卖后买，避免自成交
            chunk_sell = sorted(
                [k for k in chunk if k[0] == "sell"], key=lambda x: x[1], reverse=True
            )
            chunk_buy = sorted(
                [k for k in chunk if k[0] == "buy"], key=lambda x: x[1], reverse=True
            )
            ordered = chunk_sell + chunk_buy
            payloads = []
            for side, lv in ordered:
                price = targets[(side, lv)]
                if side == "buy" and price >= sell1_t:
                    price = round_px(sell1_t - tick, self.price_prec)
                if side == "sell" and price <= buy1_t:
                    price = round_px(buy1_t + tick, self.price_prec)
                payloads.append(self.make_order_payload(side, price, lv))
            sns = self.place_batch(payloads)
            for k, sn, o in zip(ordered, sns, payloads):
                self.tracked[k] = sn
                self.tracked_price[k] = float(o["price"])
            time.sleep(0.05)
        print(
            "[SYNC] replace={} missing={} tracked={}".format(
                len(need_replace), len(missing), len(self.tracked)
            )
        )

    def run(self) -> None:
        self.last_yaml_reload = time.time()
        self.ensure_precision()
        self.init_mid()
        assert self.mid is not None
        self.last_bnb = fetch_binance_price(self.binance_host, self.ref_symbol)
        buys, sells = build_ladder(
            self.mid, self.order_count, self.price_ratio, self.price_prec
        )
        print(
            "[LADDER] buy1={} sell1={} buy_far={} sell_far={}".format(
                buys[0], sells[0], buys[-1], sells[-1]
            )
        )
        self.cancel_all_open()
        self.bootstrap_orders(buys, sells)

        while True:
            t0 = time.time()
            try:
                self.maybe_reload_yaml()
                self.update_mid_from_bnb()
                assert self.mid is not None
                buys, sells = build_ladder(
                    self.mid, self.order_count, self.price_ratio, self.price_prec
                )
                self.sync_orders(buys, sells)
            except Exception:
                print("[LOOP-ERR]\n{}".format(traceback.format_exc()))
            elapsed = time.time() - t0
            time.sleep(max(0.2, self.loop_interval - elapsed))


def parse_args():
    p = argparse.ArgumentParser(description="WBS 跟 BNB 波动铺单")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="yaml 配置路径")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not os.path.isfile(args.config):
        print("配置不存在: {}".format(args.config))
        return 2
    try:
        WbsBnbMaker(args.config).run()
    except KeyboardInterrupt:
        print("\n退出")
        return 0
    except Exception as e:
        print("启动失败: {}".format(e))
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
