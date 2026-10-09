import asyncio
import traceback
import aiohttp


class RequestSession:
    def __init__(self):
        self.client = None

    def __del__(self):
        if self.client:
            asyncio.run(self.client.close())

    @property
    def request(self):
        if self.client is None:
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            self.client = aiohttp.ClientSession(connector=connector)
        return self.client


G_RequestSession = RequestSession()
