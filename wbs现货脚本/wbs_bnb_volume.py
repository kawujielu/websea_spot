#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WBS 自刷量脚本

- 优先 /openApi/entrust/brush；公共 oapi 若 404 则自动改同价买卖对敲
- 价格：盘口买一~卖一之间随机
- 间隔：2~10 秒随机（落后加急偏短，超前放慢偏长）
- 日目标：首日 400 万 USDT，每天 *0.98，最低 10 万后固定
- 控速：尽量贴近日目标（参考 ±1% 节奏）；可以少；即使略超也绝不停止，继续刷
- 跨日后立刻按新日目标继续

用法：
  pip3 install requests pyyaml
  python3 wbs_bnb_volume.py
  python3 wbs_bnb_volume.py --config wbs_bnb_volume.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
import time
import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "wbs_bnb_volume.yaml")
DEFAULT_STATE = os.path.join(SCRIPT_DIR, "wbs_bnb_volume.state.json")

DAY_SECONDS = 24 * 3600


def digit_to_string(d: float, prec: Optional[int] = None) -> str:
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


def cfg_get(cfg: dict, key: str, default=None):
    v = cfg.get(key, default)
    return default if v is None or v == "" else v


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ValueError("yaml 根节点必须是 map")
    return cfg


def parse_date(s: str) -> date:
    return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# API
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
            "User-Agent": "wbs_bnb_volume/1.0",
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

    def precision(self, symbol: str) -> Dict[str, Any]:
        res = self.request("GET", "/openApi/market/precision")
        if res.get("errno") != 0:
            raise RuntimeError("precision 失败: {}".format(res))
        result = res.get("result") or {}
        if symbol in result:
            return result[symbol]
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

    def brush(self, symbol: str, amount: str, price: str) -> dict:
        """自刷量：POST /openApi/entrust/brush（多为做市内网接口）"""
        return self.request(
            "POST",
            "/openApi/entrust/brush",
            {"symbol": symbol, "amount": amount, "price": price},
        )

    def add(self, symbol: str, order_type: str, amount: str, price: str) -> dict:
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

    def cancel(self, order_ids: list, symbol: str = "") -> dict:
        data = {"order_ids": ",".join(order_ids)}
        if symbol:
            data["symbol"] = symbol
        res = self.request("POST", "/v1/spot/order/cancel", data)
        if res.get("errno") == 404:
            res = self.request("POST", "/openApi/entrust/cancel", data)
        return res


# ---------------------------------------------------------------------------
# 日目标 / 状态
# ---------------------------------------------------------------------------
def daily_target_usdt(
    start: date, today: date, day1: float, decay: float, floor: float
) -> Tuple[int, float]:
    """返回 (第几天从1起, 当日目标USDT)。"""
    day_idx = max(1, (today - start).days + 1)
    target = float(day1) * (float(decay) ** (day_idx - 1))
    if target < float(floor):
        target = float(floor)
    return day_idx, target


class VolumeState:
    def __init__(self, path: str):
        self.path = path
        self.data: dict = {
            "day": "",
            "filled_usdt": 0.0,
            "trade_count": 0,
            "start_date": "",
        }
        self.load()

    def load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            if isinstance(raw, dict):
                self.data.update(raw)
        except Exception as e:
            print("[STATE] 读取失败，忽略: {}".format(e))

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def ensure_day(self, today: date, start_date: date) -> None:
        day_s = today.isoformat()
        if self.data.get("day") != day_s:
            print(
                "[STATE] 换日 {} -> {} 昨日filled={}".format(
                    self.data.get("day") or "-",
                    day_s,
                    round(float(self.data.get("filled_usdt") or 0), 2),
                )
            )
            self.data["day"] = day_s
            self.data["filled_usdt"] = 0.0
            self.data["trade_count"] = 0
        if not self.data.get("start_date"):
            self.data["start_date"] = start_date.isoformat()
        self.save()

    @property
    def filled(self) -> float:
        return float(self.data.get("filled_usdt") or 0)

    def add_fill(self, usdt: float) -> None:
        self.data["filled_usdt"] = self.filled + float(usdt)
        self.data["trade_count"] = int(self.data.get("trade_count") or 0) + 1
        self.save()


# ---------------------------------------------------------------------------
# 策略
# ---------------------------------------------------------------------------
class WbsVolumeBrush:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.cfg: dict = {}
        self.api: Optional[SpotApi] = None
        self.price_prec = 8
        self.amount_prec = 6
        self.min_quantity = 0.0
        self.max_quantity = 0.0
        self.state = VolumeState(DEFAULT_STATE)
        self.last_yaml_reload = 0.0
        # brush 不可用时自动切对敲；yaml 可强制 use_brush: false
        self.use_brush = True
        self._apply_config(load_config(config_path), first=True)

    def _apply_config(self, cfg: dict, first: bool = False) -> None:
        self.cfg = cfg
        host = str(cfg_get(cfg, "host", "https://oapi.websea.com"))
        token = str(cfg_get(cfg, "token", "") or "")
        secret = str(cfg_get(cfg, "secret_key", "") or "")
        self.symbol = str(cfg_get(cfg, "symbol", "WBS-USDT"))
        self.dry_run = bool(cfg_get(cfg, "dry_run", True))
        self.yaml_reload_sec = float(cfg_get(cfg, "yaml_reload_sec", 300))
        # 仅当 yaml 显式配置时覆盖；运行中因 404 关掉后，热加载若未写 false 则保持关掉
        if "use_brush" in cfg and cfg.get("use_brush") is not None and cfg.get("use_brush") != "":
            self.use_brush = bool(cfg_get(cfg, "use_brush", True))

        self.day1_target = float(cfg_get(cfg, "day1_target_usdt", 4_000_000))
        self.daily_decay = float(cfg_get(cfg, "daily_decay", 0.98))
        self.daily_floor = float(cfg_get(cfg, "daily_floor_usdt", 100_000))
        self.tolerance = float(cfg_get(cfg, "tolerance", 0.01))  # ±1%
        self.interval_min = float(cfg_get(cfg, "interval_min_sec", 2))
        self.interval_max = float(cfg_get(cfg, "interval_max_sec", 10))
        if self.interval_min > self.interval_max:
            self.interval_min, self.interval_max = self.interval_max, self.interval_min
        # 单笔 USDT 名义上限；超限则在 [fallback_min, fallback_max] U 随机
        self.usdt_hard_max = float(cfg_get(cfg, "usdt_hard_max", 500))
        self.usdt_fallback_min = float(cfg_get(cfg, "usdt_fallback_min", 10))
        self.usdt_fallback_max = float(cfg_get(cfg, "usdt_fallback_max", 250))
        if self.usdt_fallback_min > self.usdt_fallback_max:
            self.usdt_fallback_min, self.usdt_fallback_max = (
                self.usdt_fallback_max,
                self.usdt_fallback_min,
            )

        start_s = cfg_get(cfg, "start_date", None)
        if start_s:
            self.start_date = parse_date(str(start_s))
        elif self.state.data.get("start_date"):
            self.start_date = parse_date(self.state.data["start_date"])
        else:
            self.start_date = date.today()

        state_path = str(cfg_get(cfg, "state_file", DEFAULT_STATE))
        if not os.path.isabs(state_path):
            state_path = os.path.join(SCRIPT_DIR, state_path)
        if os.path.abspath(state_path) != os.path.abspath(self.state.path):
            self.state = VolumeState(state_path)

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

        print(
            "[CFG] symbol={} day1={} decay={} floor={} tol±{}% interval={}~{}s use_brush={} dry_run={} start={}".format(
                self.symbol,
                self.day1_target,
                self.daily_decay,
                self.daily_floor,
                self.tolerance * 100,
                self.interval_min,
                self.interval_max,
                self.use_brush,
                self.dry_run,
                self.start_date.isoformat(),
            )
        )

    def maybe_reload_yaml(self) -> None:
        now = time.time()
        if now - self.last_yaml_reload < self.yaml_reload_sec:
            return
        try:
            self._apply_config(load_config(self.config_path), first=False)
            self.last_yaml_reload = now
            print("[CFG] yaml 已热加载 {}".format(time.strftime("%H:%M:%S")))
        except Exception as e:
            print("[CFG] 热加载失败: {}".format(e))

    def ensure_precision(self) -> None:
        if not self.api:
            return
        if (
            cfg_get(self.cfg, "price_precision") is not None
            and cfg_get(self.cfg, "amount_precision") is not None
        ):
            return
        prec = self.api.precision(self.symbol)
        if cfg_get(self.cfg, "price_precision") is None:
            self.price_prec = int(prec.get("price", self.price_prec))
        if cfg_get(self.cfg, "amount_precision") is None:
            self.amount_prec = int(prec.get("amount", self.amount_prec))
        self.min_quantity = float(prec.get("minQuantity") or 0)
        self.max_quantity = float(prec.get("maxQuantity") or 0)
        print(
            "[PREC] price={} amount={} minQ={} maxQ={}".format(
                self.price_prec, self.amount_prec, self.min_quantity, self.max_quantity
            )
        )

    def get_bid_ask(self) -> Tuple[float, float]:
        if not self.api:
            raise RuntimeError("无 API，无法读盘口")
        depth = self.api.depth(self.symbol)
        bids = depth.get("bids") or []
        asks = depth.get("asks") or []
        if not bids or not asks:
            raise RuntimeError("盘口为空")
        bid1 = float(bids[0][0])
        ask1 = float(asks[0][0])
        if ask1 <= bid1:
            raise RuntimeError("盘口异常 bid={} ask={}".format(bid1, ask1))
        return bid1, ask1

    def random_price(self, bid1: float, ask1: float) -> float:
        tick = tick_size(self.price_prec)
        lo = bid1 + tick
        hi = ask1 - tick
        if hi <= lo:
            # 买卖一只差 1 tick：取中间
            mid = round_px((bid1 + ask1) / 2.0, self.price_prec)
            if mid <= bid1:
                mid = round_px(bid1 + tick, self.price_prec)
            if mid >= ask1:
                mid = round_px(ask1 - tick, self.price_prec)
            return mid
        # 在 (bid, ask) 内按 tick 网格随机
        n_lo = int(round(lo / tick))
        n_hi = int(round(hi / tick))
        if n_hi < n_lo:
            n_hi = n_lo
        n = random.randint(n_lo, n_hi)
        return round_px(n * tick, self.price_prec)

    def seconds_into_day(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now()
        midn = datetime.combine(now.date(), datetime.min.time())
        return max(0.0, (now - midn).total_seconds())

    def ideal_filled(self, target: float, now: Optional[datetime] = None) -> float:
        """按时间线性进度的理想累计成交。"""
        elapsed = self.seconds_into_day(now)
        return target * min(1.0, elapsed / DAY_SECONDS)

    def pick_notional(self, target: float, filled: float, price: float) -> float:
        """
        选下一笔 USDT 名义（永不因超目标而停刷）：
        - 跟随理想进度：落后加大、超前缩小
        - 已达/超过目标：改用小单继续刷
        - 允许最终少于目标；略超也继续
        """
        ideal = self.ideal_filled(target)
        avg_iv = (self.interval_min + self.interval_max) / 2.0
        remain_sec = max(avg_iv, DAY_SECONDS - self.seconds_into_day())
        est_trades = max(1.0, remain_sec / avg_iv)

        gap = ideal - filled  # >0 落后于时间进度
        to_target = max(0.0, target - filled)
        min_one = max(
            1.0, self.min_quantity * price if self.min_quantity and price else 1.0
        )
        # 单笔上限：日目标的 0.5%，避免单笔过大导致偏离过大
        max_one = max(target * 0.005, min_one * 2)

        if to_target > 0:
            # 尚未到目标：按剩余额度/剩余笔数均摊
            base = to_target / est_trades
            if gap > 0:
                scale = 1.0 + min(1.5, gap / max(target * self.tolerance, 1.0))
            else:
                # 超前于时间线：缩小，但继续刷
                scale = max(0.25, 1.0 + gap / max(target * self.tolerance * 2, 1.0))
            jitter = random.uniform(0.5, 1.5)
            notional = base * scale * jitter
        else:
            # 已达/超过目标：小单继续刷（不停止）
            # 参考目标 1% 量级的小单，再随机
            notional = max(min_one, target * self.tolerance * random.uniform(0.05, 0.2))
            # 超越多，单笔越偏小
            over_ratio = (filled - target) / max(target, 1.0)
            shrink = max(0.15, 1.0 - min(0.85, over_ratio * 5))
            notional *= shrink

        notional = max(min_one, min(notional, max_one))
        return notional

    def _quantize_amount(self, val: float) -> float:
        if self.amount_prec > 0:
            q = Decimal(10) ** -int(self.amount_prec)
            return float(Decimal(str(val)).quantize(q, rounding=ROUND_DOWN))
        return float(int(round(val)))

    def notional_to_amount(self, notional: float, price: float) -> float:
        if price <= 0:
            return 0.0
        amt = Decimal(str(notional)) / Decimal(str(price))
        if self.amount_prec > 0:
            q = Decimal(10) ** -int(self.amount_prec)
            amt = amt.quantize(q, rounding=ROUND_DOWN)
        else:
            amt = amt.to_integral_value(rounding=ROUND_DOWN)
        val = float(amt)
        if self.min_quantity and val < self.min_quantity:
            return 0.0
        if self.max_quantity and val > self.max_quantity:
            val = self._quantize_amount(self.max_quantity)
        return val

    def clamp_trade_usdt(self, notional: float) -> float:
        """单笔 USDT 不得超过 usdt_hard_max；超出则在 fallback 区间(U)随机。"""
        if notional <= 0:
            return 0.0
        if notional <= self.usdt_hard_max:
            return notional
        lo = self.usdt_fallback_min
        hi = self.usdt_fallback_max
        hi = min(hi, self.usdt_hard_max)
        lo = min(lo, hi)
        picked = random.uniform(lo, hi)
        print(
            "[USDT-CLAMP] notional {}U > {}U，改为随机 {}U".format(
                round(notional, 4), self.usdt_hard_max, round(picked, 4)
            )
        )
        return picked

    def pick_interval(self, target: float, filled: float) -> float:
        ideal = self.ideal_filled(target)
        gap = ideal - filled  # >0 落后
        # 归一化到 [-1, 1]
        norm = max(-1.0, min(1.0, gap / max(target * 0.02, 1.0)))
        # 落后 -> 偏短间隔；超前 -> 偏长
        t = (1.0 - norm) / 2.0  # 落后 norm=1 -> t=0 短；超前 norm=-1 -> t=1 长
        base = self.interval_min + (self.interval_max - self.interval_min) * t
        # 小幅随机
        lo = max(self.interval_min, base * 0.8)
        hi = min(self.interval_max, base * 1.2)
        if hi < lo:
            hi = lo
        return random.uniform(lo, hi)

    @staticmethod
    def _resp_str(res: dict) -> str:
        try:
            return json.dumps(res, ensure_ascii=False)
        except Exception:
            return str(res)

    @staticmethod
    def _order_sn(res: dict) -> str:
        result = res.get("result") or {}
        if isinstance(result, dict):
            return str(result.get("order_sn") or result.get("id") or "")
        return ""

    def do_cross(self, amount: float, price: float) -> Tuple[bool, float]:
        """同价先卖后买对敲（公共 oapi 兜底）。返回 (成功?, 名义USDT)。"""
        amt_s = digit_to_string(amount, self.amount_prec)
        px_s = digit_to_string(price, self.price_prec)
        usdt = float(amount) * float(price)
        if self.dry_run or not self.api:
            print(
                "[DRY-CROSS] sell+buy amount={} price={} usdt~{}".format(
                    amt_s, px_s, round(usdt, 4)
                )
            )
            print(
                "[DRY-CROSS] resp {}".format(
                    json.dumps(
                        {
                            "errno": 0,
                            "errmsg": "dry_run",
                            "result": {"amount": amt_s, "price": px_s, "usdt": round(usdt, 4)},
                        },
                        ensure_ascii=False,
                    )
                )
            )
            return True, usdt

        # 先挂卖，再挂买，促使同价成交
        sell_res = self.api.add(self.symbol, "sell-limit", amt_s, px_s)
        print(
            "[CROSS-SELL] req amount={} price={} usdt~{}".format(
                amt_s, px_s, round(usdt, 4)
            )
        )
        print("[CROSS-SELL] resp {}".format(self._resp_str(sell_res)))
        if sell_res.get("errno") != 0:
            return False, 0.0
        sell_sn = self._order_sn(sell_res)

        buy_res = self.api.add(self.symbol, "buy-limit", amt_s, px_s)
        print(
            "[CROSS-BUY] req amount={} price={} usdt~{}".format(
                amt_s, px_s, round(usdt, 4)
            )
        )
        print("[CROSS-BUY] resp {}".format(self._resp_str(buy_res)))
        if buy_res.get("errno") != 0:
            if sell_sn:
                try:
                    c_res = self.api.cancel([sell_sn], symbol=self.symbol)
                    print("[CROSS-CANCEL] sell sn={} resp {}".format(sell_sn, self._resp_str(c_res)))
                except Exception as e:
                    print("[CROSS-CANCEL] sell sn={} err={}".format(sell_sn, e))
            return False, 0.0
        return True, usdt

    def do_brush(self, amount: float, price: float) -> Tuple[bool, float]:
        """优先 brush；404 后永久切对敲。返回 (成功?, 名义USDT)。"""
        amt_s = digit_to_string(amount, self.amount_prec)
        px_s = digit_to_string(price, self.price_prec)
        usdt = float(amount) * float(price)

        if not self.use_brush:
            return self.do_cross(amount, price)

        if self.dry_run or not self.api:
            dry_res = {
                "errno": 0,
                "errmsg": "dry_run",
                "result": {
                    "symbol": self.symbol,
                    "amount": amt_s,
                    "price": px_s,
                    "usdt": round(usdt, 4),
                    "mode": "brush",
                },
            }
            print("[DRY-BRUSH] req amount={} price={} usdt~{}".format(amt_s, px_s, round(usdt, 4)))
            print("[DRY-BRUSH] resp {}".format(json.dumps(dry_res, ensure_ascii=False)))
            return True, usdt

        res = self.api.brush(self.symbol, amt_s, px_s)
        print(
            "[BRUSH] req symbol={} amount={} price={} usdt~{}".format(
                self.symbol, amt_s, px_s, round(usdt, 4)
            )
        )
        print("[BRUSH] resp {}".format(self._resp_str(res)))

        if res.get("errno") == 0:
            return True, usdt

        if res.get("errno") == 404:
            self.use_brush = False
            print("[BRUSH] 接口不可用(404)，之后改用同价买卖对敲")
            return self.do_cross(amount, price)

        return False, 0.0

    def run_once(self) -> float:
        """执行一笔；返回建议 sleep 秒数。永不因超目标停刷。"""
        today = date.today()
        self.state.ensure_day(today, self.start_date)
        day_idx, target = daily_target_usdt(
            self.start_date, today, self.day1_target, self.daily_decay, self.daily_floor
        )
        filled = self.state.filled

        bid1, ask1 = self.get_bid_ask()
        price = self.random_price(bid1, ask1)
        notional = self.pick_notional(target, filled, price)
        notional = self.clamp_trade_usdt(notional)
        amount = self.notional_to_amount(notional, price)
        if amount <= 0:
            return random.uniform(self.interval_min, self.interval_max)

        ok, filled_usdt = self.do_brush(amount, price)
        if ok and filled_usdt > 0:
            self.state.add_fill(filled_usdt)
            filled = self.state.filled
            pct = (filled / target - 1.0) * 100 if target else 0
            print(
                "[PROG] day{} target={} filled={} ({:+.3f}% vs target) bid={} ask={} px={}".format(
                    day_idx,
                    round(target, 2),
                    round(filled, 2),
                    pct,
                    bid1,
                    ask1,
                    price,
                )
            )

        return self.pick_interval(target, self.state.filled)

    def run(self) -> None:
        self.last_yaml_reload = time.time()
        self.ensure_precision()
        self.state.ensure_day(date.today(), self.start_date)
        day_idx, target = daily_target_usdt(
            self.start_date,
            date.today(),
            self.day1_target,
            self.daily_decay,
            self.daily_floor,
        )
        print(
            "[START] day{} target={} filled={} start_date={}".format(
                day_idx, round(target, 2), round(self.state.filled, 2), self.start_date
            )
        )
        while True:
            t0 = time.time()
            try:
                self.maybe_reload_yaml()
                sleep_s = self.run_once()
            except Exception:
                print("[LOOP-ERR]\n{}".format(traceback.format_exc()))
                sleep_s = random.uniform(self.interval_min, self.interval_max)
            elapsed = time.time() - t0
            time.sleep(max(0.2, sleep_s - elapsed))


def parse_args():
    p = argparse.ArgumentParser(description="WBS 自刷量（brush）")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="yaml 配置路径")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not os.path.isfile(args.config):
        print("配置不存在: {}".format(args.config))
        return 2
    try:
        WbsVolumeBrush(args.config).run()
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
