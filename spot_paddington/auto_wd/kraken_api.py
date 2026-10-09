import asyncio
import time
import hmac
import hashlib
import json
import base64
import urllib.parse

import loguru

from many_configs.account_config import EXTERNAL_ACCOUNTS
from scaffold.aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.recode_msg import recode_error_msg


class KrakenApi:
    """Kraken REST — POST /0/private/DepositStatus"""

    exchange_name = "kraken"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]["spot_restful"]
        self._deposit_endpoint = "/0/private/DepositStatus"

    def _get_kraken_signature(self, urlpath: str, data: dict, nonce: str) -> str:
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self._secret_), message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    async def request(self, args):
        data = dict(args.get("data") or {})
        method = args["method"]
        signed = args.get("signed", False)
        endpoint = args["url"]
        url = self.url + endpoint

        headers = {
            "User-Agent": "Kraken Python Client",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        if signed:
            nonce = str(int(time.time() * 1000))
            data["nonce"] = nonce
            headers["API-Key"] = self._apiKey_
            headers["API-Sign"] = self._get_kraken_signature(endpoint, data, nonce)

        async with G_RequestSession.request.request(
            method=method,
            url=url,
            headers=headers,
            data=urllib.parse.urlencode(data) if data else None,
            timeout=args.get("timeout", 10),
        ) as r:
            return {"content": await r.text(), "code": r.status}

    async def deposit_hisrec(self, start_ts, asset=None, limit=500):
        """
        POST /0/private/DepositStatus — 查询近期充值记录。
        文档: https://docs.kraken.com/api-reference/funding/get-status-of-recent-deposits

        :param start_ts: 起始时间（毫秒），与 bn_api.deposit_hisrec 一致
        :param asset: 可选，Kraken 资产名（如 USDT、XBT）
        :param limit: 每页条数，默认 500
        :return: 充值记录列表；status 为 Success / Settled 表示已入账
        """
        data = {
            "start": str(int(start_ts // 1000)),
            "end": str(int(time.time())),
            "limit": limit,
        }
        if asset:
            data["asset"] = asset

        args = {
            "url": self._deposit_endpoint,
            "method": "POST",
            "signed": True,
            "data": data,
            "timeout": 10,
        }
        result = await self.request(args)
        if result["code"] != 200:
            msg = f"deposit_hisrec error {start_ts} {result}"
            await recode_error_msg(msg, "spot_hedge")
            return None

        payload = json.loads(result["content"])
        if payload.get("error"):
            msg = f"deposit_hisrec kraken error {start_ts} {payload['error']}"
            loguru.logger.error(msg)
            await recode_error_msg(msg, "spot_hedge")
            return None

        his = payload.get("result")
        if isinstance(his, dict) and "deposit" in his:
            his = his["deposit"]
        loguru.logger.info(f"deposit_hisrec {start_ts=} count={len(his) if his else 0}")
        return his


kraken_instance = KrakenApi()


if __name__ == "__main__":
    asyncio.run(kraken_instance.deposit_hisrec(start_ts=int(time.time() * 1000) - 86400 * 1000))
