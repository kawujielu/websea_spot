"""精简版 AbcApi，供下架币对批量撤单脚本使用。仅标准库，无项目内依赖。"""
import asyncio
import hashlib
import json
import random
import ssl
import string
import time
import urllib.error
import urllib.parse
import urllib.request

# 生产环境；测试环境改为 https://exq.wbstests.net
HOST = "https://exqv.websea.work"


class AbcApi:

    def __init__(self, token, secret_key, host=HOST):
        self.host = host.rstrip("/")
        self._token_ = token
        self._secret_key_ = secret_key
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._ssl_ctx = ctx

    def sign(self, nonce, data):
        parts = [self._token_, self._secret_key_, nonce]
        parts += [f"{k}={v}" for k, v in data.items()]
        return hashlib.sha1("".join(sorted(parts)).encode()).hexdigest()

    def mk_header(self, data):
        nonce = f"{int(time.time() * 1000)}_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
        return {"Token": self._token_, "Nonce": nonce, "Signature": self.sign(nonce, data)}

    def _sync_request(self, method, path, data=None, timeout=3):
        data = data or {}
        url = f"{self.host}{path}"
        headers = self.mk_header(data)
        if method == "GET":
            qs = urllib.parse.urlencode(data)
            req = urllib.request.Request(f"{url}?{qs}" if qs else url, headers=headers, method="GET")
        else:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
                return {"code": resp.status, "content": resp.read().decode()}
        except urllib.error.HTTPError as e:
            return {"code": e.code, "content": e.read().decode()}

    async def request(self, args):
        url = args["url"]
        path = url[len(self.host):] if url.startswith(self.host) else url
        return await asyncio.to_thread(
            self._sync_request,
            args.get("method", "GET").upper(),
            path,
            args.get("data") or {},
            args.get("timeout", 3),
        )

    async def current_list(self, symbol, order_sn=None, direct="pre", limit=100):
        data = {"symbol": symbol, "direct": direct, "limit": limit}
        if order_sn:
            data["from"] = order_sn
        result = await self.request({"url": f"{self.host}/openApi/entrust/currentList", "data": data})
        if result["code"] == 200:
            return json.loads(result["content"])
        print("current_list", result)

    async def cancel(self, order_ids=None, symbol=None):
        data = {}
        if order_ids:
            data["order_ids"] = ",".join(order_ids)
        if symbol:
            data["symbol"] = symbol
        result = await self.request({"url": f"{self.host}/openApi/entrust/cancel", "method": "POST", "data": data})
        if result["code"] == 200:
            return json.loads(result["content"])
        return {"errno": -1, "msg": f"现货 symbol={symbol} 撤单异常"}
