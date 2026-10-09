import time
import os
import sys
import traceback
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs import heartbeat, sendmessage

while True:
    try:
        # 步骤1: 获取 BTC/USD 价格
        btc_url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'
        btc_response = requests.get(btc_url)
        btc_price = btc_response.json()['bitcoin']['usd'] if btc_response.status_code == 200 else 70000  # 备用值

        # 步骤2: 获取交易所列表
        url = 'https://api.coingecko.com/api/v3/exchanges'
        params = {
            'per_page': 250,
            'page': 1,
            'order': 'volume_desc'
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()

            websea_exchange = next((ex for ex in data if ex['id'] == 'websea'), None)

            if websea_exchange:
                volume_24h_btc = websea_exchange['trade_volume_24h_btc']
                volume_24h_usd = volume_24h_btc * btc_price
                if volume_24h_usd < 2208456425:
                    mess = "成交量异常 ， 检查cmc成交量"
                    sendmessage.send_telegram_msg(message=mess, ser='Alarm')
                name = websea_exchange['name']
                print(f"交易所: {name}")
                print(f"BTC 价格: ${btc_price:,.2f} USD")
                print(f"24h 现货交易量: ${volume_24h_usd:,.2f} USD")
            else:
                print("未找到 Websea。")
        else:
            print(f"请求失败: {response.status_code}")
    except:
        print(f"{traceback.format_exc()}")
    finally:
        print(f"sleep 10 s")
        time.sleep(600)
