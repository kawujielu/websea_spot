import asyncio
import time
import hmac
import hashlib
import json

import loguru

from many_configs.account_config import EXTERNAL_ACCOUNTS
from scaffold.aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.recode_msg import recode_error_msg


class GateApi:
    """Gate API v4 — wallet deposits / withdrawals"""

    exchange_name = "gate"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]["spot_restful"]
        self.prefix = "/api/v4"

    def _gen_sign(self, method, url_path, timestamp, query_string="", payload_string=""):
        hashed_payload = hashlib.sha512((payload_string or "").encode("utf-8")).hexdigest()
        sign_string = f"{method}\n{url_path}\n{query_string}\n{hashed_payload}\n{timestamp}"
        return hmac.new(self._secret_.encode("utf-8"), sign_string.encode("utf-8"), hashlib.sha512).hexdigest()

    def _parse_params_to_str(self, data: dict) -> str:
        if not data:
            return ""
        parts = [f"{k}={v}" for k, v in data.items()]
        return "?" + "&".join(parts)

    async def request(self, args):
        data = args.get("data") or {}
        method = args["method"]
        signed = args.get("signed", False)
        timeout = args.get("timeout", 15)
        timestamp = str(time.time())
        request_path = self._parse_params_to_str(data) if method != "POST" else ""
        query_string = request_path.replace("?", "") if request_path else ""
        body = json.dumps(data) if method == "POST" else ""
        host_path = args["url"].replace(self.url, "")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        if signed:
            headers["KEY"] = self._apiKey_
            headers["Timestamp"] = timestamp
            headers["SIGN"] = self._gen_sign(method, host_path, timestamp, query_string, body)

        async with G_RequestSession.request.request(
            method=method,
            url=args["url"],
            params=query_string,
            data=body,
            headers=headers,
            timeout=timeout,
        ) as r:
            return {"content": await r.text(), "code": r.status}

    async def deposit_hisrec(self, start_ts, currency=None, limit=500):
        """
        GET /wallet/deposits — 查询充值记录。
        :param start_ts: 起始时间（毫秒），与 bn_api.deposit_hisrec 一致
        :param currency: 可选，币种
        :param limit: 最大条数，默认 500
        :return: Gate DepositRecord 列表；status=DONE 表示已入账
        """
        data = {
            "from": int(start_ts // 1000),
            "to": int(time.time()),
            "limit": limit,
        }
        if currency:
            data["currency"] = currency

        args = {
            "url": f"{self.url}{self.prefix}/wallet/deposits",
            "method": "GET",
            "signed": True,
            "data": data,
            "timeout": 10,
        }
        result = await self.request(args)
        if result["code"] == 200:
            his = json.loads(result["content"])
            loguru.logger.info(f"deposit_hisrec {start_ts=} {his=}")
            return his

        msg = f"deposit_hisrec error {start_ts} {result}"
        await recode_error_msg(msg, "spot_hedge")
        return None

    async def withdraw_hisrec(self, start_ts, currency=None, limit=100):
        """
        GET /wallet/withdrawals — 查询提币记录。
        :param start_ts: 起始时间（毫秒），与 deposit_hisrec 一致
        :param currency: 可选，币种
        :param limit: 单页最大条数，默认 100（接口上限）
        :return: Gate WithdrawalRecord 列表；status=DONE 表示已完成
        注意: 时间跨度不能超过 30 天
        """
        data = {
            "from": int(start_ts // 1000),
            "to": int(time.time()),
            "limit": limit,
        }
        if currency:
            data["currency"] = currency

        args = {
            "url": f"{self.url}{self.prefix}/wallet/withdrawals",
            "method": "GET",
            "signed": True,
            "data": data,
            "timeout": 10,
        }
        result = await self.request(args)
        if result["code"] == 200:
            his = json.loads(result["content"])
            loguru.logger.info(f"withdraw_hisrec {start_ts=} {his=}")
            return his

        msg = f"withdraw_hisrec error {start_ts} {result}"
        await recode_error_msg(msg, "spot_hedge")
        return None


gate_instance = GateApi()


if __name__ == "__main__":
    start = int(time.time() * 1000) - 86400 * 1000
    asyncio.run(gate_instance.withdraw_hisrec(start_ts=start))
