"""
独立调用 Binance 现货 account（账户权益/余额）与 get_open_orders（当前委托）。

不导入 exchanges/restful_api/binance.py，因此不依赖 libs、load、many_configs。

运行:
  python scripts/run_binance_wallet_and_open_orders.py

所有参数均在下方「配置」区修改，无需命令行或环境变量。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from operator import itemgetter
from typing import Any

import aiohttp

# ========== 配置（按需修改） ==========
API_KEY = "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE"
SECRET = "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU"
BASE_URL = "https://api.binance.com"  # 测试网: https://testnet.binance.vision
SYMBOL = None  # 如 "BTC-USDT"；None 表示查询全部当前委托
REQUEST_TIMEOUT = 15


def _order_params(data: dict) -> list[tuple[str, Any]]:
    has_signature = False
    params: list[tuple[str, Any]] = []
    for key, value in data.items():
        if key == "signature":
            has_signature = True
        else:
            params.append((key, value))
    params.sort(key=itemgetter(0))
    if has_signature:
        params.append(("signature", data["signature"]))
    return params


def _generate_signature(secret: str, data: dict) -> str:
    ordered_data = _order_params(data)
    query_string = "&".join(f"{k}={v}" for k, v in ordered_data)
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()


class BinanceSpotLite:
    """与 binance.BinanceApi 中 wallet / get_open_orders 请求与签名字段一致。"""

    def __init__(self, session: aiohttp.ClientSession, api_key: str, secret: str, base_url: str):
        self._session = session
        self._api_key = api_key
        self._secret = secret
        self.url = base_url.rstrip("/")

    async def _request(
        self, path: str, method: str, data: dict | None, signed: bool, timeout: int = REQUEST_TIMEOUT
    ) -> dict[str, Any]:
        payload = dict(data or {})
        if signed:
            payload["timestamp"] = int(time.time() * 1000)
            payload["signature"] = _generate_signature(self._secret, payload)

        ordered = _order_params(payload)
        ordered = [(k, v) for k, v in ordered if v is not None]
        query_string = "&".join(f"{k}={v}" for k, v in ordered)
        url = f"{self.url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "binance/python",
            "X-MBX-APIKEY": self._api_key,
        }
        async with self._session.request(method, url, headers=headers, timeout=timeout) as r:
            text = await r.text()
            return {"code": r.status, "content": text}

    async def account_equity(self) -> dict[str, Any]:
        """GET /api/v3/account — 各资产 free/locked/total 及汇总 wallet。"""
        result = await self._request("/api/v3/account", "GET", {}, signed=True)
        if result["code"] != 200:
            return result

        raw = json.loads(result["content"])
        balances: dict[str, dict[str, float]] = {}
        wallet: dict[str, float] = {}
        for item in raw.get("balances", []):
            free = float(item["free"])
            locked = float(item["locked"])
            if not free and not locked:
                continue
            asset = item["asset"]
            total = free + locked
            balances[asset] = {"free": free, "locked": locked, "total": total}
            wallet[asset] = total

        return {
            "canTrade": raw.get("canTrade"),
            "canWithdraw": raw.get("canWithdraw"),
            "canDeposit": raw.get("canDeposit"),
            "updateTime": raw.get("updateTime"),
            "balances": balances,
            "wallet": wallet,
        }

    async def wallet(self) -> dict[str, float] | dict[str, Any]:
        """与 BinanceApi.wallet 一致：资产 -> free + locked。"""
        equity = await self.account_equity()
        if "wallet" in equity:
            return equity["wallet"]
        return equity

    async def get_open_orders(self, symbol: str | None = None) -> list | dict[str, Any]:
        """GET /api/v3/openOrders — symbol 可选，不传则返回全部挂单。"""
        data: dict[str, Any] = {}
        if symbol:
            data["symbol"] = symbol.replace("-", "")
        result = await self._request("/api/v3/openOrders", "GET", data, signed=True)
        if result["code"] == 200:
            return json.loads(result["content"])
        return result


async def main() -> None:
    connector = aiohttp.TCPConnector(limit=10, ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = BinanceSpotLite(session, API_KEY, SECRET, BASE_URL)
        equity = await client.account_equity()
        print("account_equity:", json.dumps(equity, indent=2, ensure_ascii=False))
        orders = await client.get_open_orders(SYMBOL)
        print("get_open_orders:", json.dumps(orders, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
