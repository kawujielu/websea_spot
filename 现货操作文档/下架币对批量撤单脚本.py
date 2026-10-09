'''
    现货下架批量撤单脚本
    版本信息:v1.0.0
    日期:2025-11-28
    作者:sky

    放在哪个目录下？？？？
'''

from abcapi_plus import AbcApi
import traceback
import asyncio


class Strategy():

    ''' ============================================================================'''
    ''' =================================== init ==================================='''
    ''' ============================================================================'''

    def __init__(self):
        self.apikey1 = {"token": "dfab8bd76d7fea39e4aa6af328cbd187", "secret_key": "l8nemtb6r1diqmksp721"}    #, "uid": 11}
        self.apikey2 = {"token": "e91f9f0f3067a0b19b1b7505643f84b0", "secret_key": "sbwcn5zty4dsqznffxgt"}    #, "uid": 12}}
        self.apikey3 = {"token": "f5050e883a7e29189298131ca32d10da", "secret_key": "2wx70l5uhzky93mzmq8s"}    #, "uid": 13}}
        self.apikey4 = {"token": "4ee5b2948440de07dc09c139835cfep3248", "secret_key": "ali6bpfyqv4lgaln4eq9"}   # , "uid": 14
        self.apikey5 = {"token": "d83e771c4d55f1fef98e34a2c43772o3330", "secret_key": "g1xo2axzjdax2ujh6twf"}   # , "uid": 15
        self.apikey6 = {"token": "027dc638e8819a3f8233645c9de076r3534", "secret_key": "rpaw214rnbgvt0vhl52j"}   # , "uid": 16
        self.apikey7 = {"token": "2ec49187f681419d1959af499d7bb0p3584", "secret_key": "wcj34ct96l2vh3s1hog7"}   # , "uid": 17
        self.symbols = ['ESP-USDT','APE-USDT','PENDLE-USDT','PUMP-USDT','GMT-USDT','IOTX-USDT','BAT-USDT','NEIRO-USDT','RAY-USDT','SAFE-USDT','FET-USDT','BOME-USDT','YGG-USDT','PEOPLE-USDT']

    async def main(self):
        for apikey in [self.apikey1, self.apikey2, self.apikey3, self.apikey4, self.apikey5, self.apikey6, self.apikey7]:
            self.task = AbcApi(**apikey)
            cancel_orders = []
            for symbol in self.symbols:
                res = await self.task.current_list(symbol=symbol)
                for i in res['result']:
                    cancel_orders.append(i['order_sn'])
                print(f"{symbol}当前订单:{cancel_orders}")
                await asyncio.sleep(1)
                # res2 = await self.task.cancel(symbol=symbol, order_ids=cancel_orders)
                # print(f"撤单信息:{res2}")

        
async def main():
    task = Strategy()
    try:
        await task.main()  # 主循环
    except:
        print(f'策略报错!\n{traceback.format_exc()}')

asyncio.run(main())
