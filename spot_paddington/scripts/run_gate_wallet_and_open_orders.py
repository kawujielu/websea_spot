"""
独立调用 Gate 现货 wallet（账户余额汇总）与 get_open_orders（订单列表）。

不导入 exchanges/restful_api/gateio.py，因此不依赖 libs、load、many_configs。

运行:
  python scripts/run_gate_wallet_and_open_orders.py

鉴权（二选一，均需提供 api key + secret）:
  - 环境变量 GATE_API_KEY、GATE_SECRET
  - 或命令行 --api-key / --secret

可选环境变量 GATE_SPOT_RESTFUL，默认 https://api.gateio.ws
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any

import aiohttp

GATE_SPOT_DEFAULT = "https://api.gateio.ws"
API_PREFIX = "/api/v4"


def _parse_params_to_str(data: dict) -> str:
    if not data:
        return ""
    parts: list[str] = []
    for key, value in data.items():
        parts.append(f"{key}={value}")
    return "&".join(parts)


def _gen_sign(secret: str, method: str, url_path: str, t: str, query_string: str, payload_string: str) -> str:
    m = hashlib.sha512()
    m.update((payload_string or "").encode("utf-8"))
    hashed_payload = m.hexdigest()
    s = "%s\n%s\n%s\n%s\n%s" % (method, url_path, query_string or "", hashed_payload, t)
    return hmac.new(secret.encode("utf-8"), s.encode("utf-8"), hashlib.sha512).hexdigest()


class GateioSpotLite:
    """与 gateio.GateioApi 中 wallet / get_open_orders 请求与签名字段一致。"""

    def __init__(self, session: aiohttp.ClientSession, api_key: str, secret: str, base_url: str):
        self._session = session
        self._api_key = api_key
        self._secret = secret
        self.url = base_url.rstrip("/")
        self.prefix = API_PREFIX

    async def _request(self, path: str, method: str, data: dict, signed: bool, timeout: int = 15) -> dict[str, Any]:
        query_string = "" if method == "POST" else _parse_params_to_str(data)
        body = json.dumps(data) if method == "POST" else ""
        full_path = f"{self.prefix}{path}"
        request_url_path = full_path
        timestamp = str(time.time())
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        if signed:
            headers["KEY"] = self._api_key
            headers["Timestamp"] = timestamp
            headers["SIGN"] = _gen_sign(self._secret, method, request_url_path, timestamp, query_string, body)

        if method == "GET":
            url = f"{self.url}{full_path}"
            if query_string:
                url = f"{url}?{query_string}"
            async with self._session.request(method, url, headers=headers, timeout=timeout) as r:
                text = await r.text()
                return {"code": r.status, "content": text}
        async with self._session.request(
            method, f"{self.url}{full_path}", data=body, headers=headers, timeout=timeout
        ) as r:
            text = await r.text()
            return {"code": r.status, "content": text}

    async def wallet(self) -> dict[str, float] | dict[str, Any]:
        result = await self._request("/spot/accounts", "GET", {}, signed=True)
        if result["code"] == 200:
            res = json.loads(result["content"])
            return {i["currency"].upper(): float(i["available"]) + float(i["locked"]) for i in res}
        return result

    async def get_open_orders(self, symbol: str, status: str) -> list | dict[str, Any]:
        pair = symbol.replace("-", "_")
        data = {"currency_pair": pair, "status": status}
        result = await self._request("/spot/orders", "GET", data, signed=True)
        if result["code"] == 200:
            return json.loads(result["content"])
        return result


def _resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    key = os.environ.get("GATE_API_KEY") or getattr(args, "api_key", None)
    secret = os.environ.get("GATE_SECRET") or getattr(args, "secret", None)
    if key and secret:
        return key, secret
    print(
        "未找到 API 凭证：请设置环境变量 GATE_API_KEY、GATE_SECRET，"
        "或使用 --api-key / --secret。本脚本不再读取 many_configs（避免依赖 load）。",
        file=sys.stderr,
    )
    raise SystemExit(2)


async def _run(symbol: str, status: str, base_url: str, api_key: str, secret: str) -> None:
    connector = aiohttp.TCPConnector(limit=10, ssl=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = GateioSpotLite(session, api_key, secret, base_url)
        balances = await client.wallet()
        print("wallet:", json.dumps(balances, indent=2, ensure_ascii=False))
        orders = await client.get_open_orders(symbol, status)
        print("get_open_orders:", json.dumps(orders, indent=2, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description="Gate 现货 wallet + 订单列表（无 libs/load 依赖）")
    p.add_argument("--symbol", default="BTC-USDT", help="交易对，如 BTC-USDT")
    p.add_argument(
        "--status",
        default="open",
        choices=("open", "finished"),
        help="open=挂单中 finished=已结束",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("GATE_SPOT_RESTFUL", GATE_SPOT_DEFAULT),
        help=f"REST 根地址，默认 {GATE_SPOT_DEFAULT}",
    )
    p.add_argument("--api-key", default='dd0eeebf5f147b1c8c1cfb5c1db2f38f', help="覆盖环境变量 GATE_API_KEY")
    p.add_argument("--secret", default='a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e', help="覆盖环境变量 GATE_SECRET")
    args = p.parse_args()
    api_key, secret = _resolve_credentials(args)
    asyncio.run(_run(args.symbol, args.status, args.base_url, api_key, secret))


if __name__ == "__main__":
    main()
