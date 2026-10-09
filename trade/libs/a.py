import asyncio
import gzip
import ssl
from ujson import dumps
from orjson import loads
import websockets
from proto_libs import PushDataV3ApiWrapper_pb2
from google.protobuf.json_format import MessageToJson

async def get_mxc_depth():
    # 订阅错误，返回数据：{'id': 0, 'code': 0, 'msg': 'no subscription success'}
    while True:
        async with websockets.connect("wss://wbs-api.mexc.com/ws", close_timeout=0.01, ping_interval=15,
                                      max_queue=128, compression=None,
                                      ) as webs:
                data = {"method": "SUBSCRIPTION","params": ["spot@public.limit.depth.v3.api.pb@BTCUSDT@5"]}

                asyncio.create_task(webs.send(dumps(data)))

                while True:
                    message = await asyncio.wait_for(webs.recv(), 3)
                    #print(message)
                    result = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
                    if isinstance(message, bytes):
                        res = result.ParseFromString(message)
                        result = loads(MessageToJson(result))
                        print(result)


if __name__ == '__main__':
    asyncio.run(get_mxc_depth())

