import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


class MongodbSession:

    def __init__(self, _mongodb_url=""):
        self.client = None
        self._mongodb_url = mongodb_url

    @property
    def async_motor_session(self):
        if self.client is None:
            self.client = AsyncIOMotorClient(self._mongodb_url).exchange.real_deal
        return self.client


mongodb_url = "mongodb://spot-ro:PcwDn46F24MHGjRa@10.60.99.86:27018/"   # prod
# mongodb_url = 'mongodb://root:0dtNu0Np5noFEFPy@172.20.0.10:27018'   # test
G_MongodbSession = MongodbSession(mongodb_url)

if __name__ == "__main__":
    async def fetch_data():
        r = await G_MongodbSession.async_motor_session.find_one({"symbol": "BTC-USDT"})


    asyncio.run(fetch_data())
