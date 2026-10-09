import redis

DB =15
# symbols = [
#     "1INCH-USDT",
#     "AAVE-USDT",
#     "ACT-USDT",
#     "AEVO-USDT",
#     "ANKR-USDT",
#     "APE-USDT",
#     "APT-USDT",
#     "ARB-USDT",
#     "ASTER-USDT",
#     "AXS-USDT",
#     "BAT-USDT",
#     "BEAMX-USDT",
#     "BMT-USDT",
#     "BNB-USDT",
#     "BOME-USDT",
#     "BTC-USDT",
#     "C-USDT",
#     "CAKE-USDT",
#     "CFX-USDT",
#     "CHZ-USDT",
#     "COMP-USDT",
#     "CRV-USDT",
#     "DOGE-USDT",
#     "DOGS-USDT",
#     "EGLD-USDT",
#     "ENA-USDT",
#     "ENS-USDT",
#     "ERA-USDT",
#     "ESP-USDT",
#     "ETH-USDT",
#     "ETHFI-USDT",
#     "EURQ-USDT",
#     "EURR-USDT",
#     "FET-USDT",
#     "FLOKI-USDT",
#     "FTT-USDT",
#     "GALA-USDT",
#     "GIGGLE-USDT",
#     "GLM-USDT",
#     "GMT-USDT",
#     "GRT-USDT",
#     "HOME-USDT",
#     "HYPER-USDT",
#     "IMX-USDT",
#     "INJ-USDT",
#     "IOTX-USDT",
#     "JASMY-USDT",
#     "JTO-USDT",
#     "JUP-USDT",
#     "KERNEL-USDT",
#     "LDO-USDT",
#     "LINK-USDT",
#     "LPT-USDT",
#     "LTC-USDT",
#     "MANA-USDT",
#     "MANTRA-USDT",
#     "MASK-USDT",
#     "MEME-USDT",
#     "MOVE-USDT",
#     "NEAR-USDT",
#     "NEIRO-USDT",
#     "NEWT-USDT",
#     "NXPC-USDT",
#     "OKB-USDT",
#     "ONDO-USDT",
#     "ORCA-USDT",
#     "ORDI-USDT",
#     "PENDLE-USDT",
#     "PENGU-USDT",
#     "PEOPLE-USDT",
#     "PEPE-USDT",
#     "PNUT-USDT",
#     "POL-USDT",
#     "PUMP-USDT",
#     "QNT-USDT",
#     "RAY-USDT",
#     "RENDER-USDT",
#     "SAFE-USDT",
#     "SAND-USDT",
#     "SHIB-USDT",
#     "SKY-USDT",
#     "SOL-USDT",
#     "SUI-USDT",
#     "SUSHI-USDT",
#     "SXT-USDT",
#     "TIA-USDT",
#     "TON-USDT",
#     "TRB-USDT",
#     "TRUMP-USDT",
#     "TRX-USDT",
#     "UNI-USDT",
#     "USDC-USDT",
#     "USDQ-USDT",
#     "USDR-USDT",
#     "W-USDT",
#     "WIF-USDT",
#     "WLD-USDT",
#     "WLFI-USDT",
#     "XAUT-USDT",
#     "XRP-USDT",
#     "YGG-USDT",
#     "ZRO-USDT",
# ]
# symbols = ['PEPE-USDT','W-USDT','DOGS-USDT','ORDI-USDT','CHZ-USDT',
#            'PENGU-USDT','GIGGLE-USDT','XAUT-USDT','APT-USDT',
#            'PNUT-USDT','COMP-USDT','CRV-USDT','BOME-USDT','W-USDT',
#            'KERNEL-USDT','TRB-USDT','MEME-USDT','SAND-USDT','AXS-USDT',
#            'ENA-USDT','MOVE-USDT','CFX-USDT','C-USDT','ARB-USDT','APE-USDT']
symbols = ['SAND-USDT']
# APT 1.3  PNUT 2.5  ZRO 2.4 CHZ 2 POL 1.4 TRB 7 COMP 2 NEIRO 2.6 MOVE 7 CFX 1.4 WLFI 1.5 BOME 4 ARB 5.5 W 6 DOGS 9 AXS 5 SAND 6 APE 3.5 C 4 LDO 5 TIA 7
# symbols = {'APT-USDT':1.3, 'PNUT-USDT':2.5, 'ZRO-USDT':2.4, 'CHZ-USDT':2, 'POL-USDT':1.4, 'TRB-USDT':7, 'COMP-USDT':2, 'NEIRO-USDT':2.6, 'MOVE-USDT':7, 'CFX-USDT':1.4, 'WLFI-USDT':1.5, 'BOME-USDT':4, 'ARB-USDT':5.5, 'W-USDT':6, 'DOGS-USDT':9, 'AXS-USDT':5, 'SAND-USDT':6, 'APE-USDT':3.5, 'C-USDT':4, 'LDO-USDT':5, 'TIA-USDT':7}



def get_redis_client():
    client = redis.Redis(
        host='market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com',        # 你的主节点或配置端点
        port=6379,                        # AWS ElastiCache Redis 默认 TLS 端口就是 6379
        db=DB,
        password='A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA',
        decode_responses=True,
        # === AWS ElastiCache 必须加的 TLS 参数 ===
        ssl=True,                         # 启用 TLS
        ssl_cert_reqs="none",             # AWS ElastiCache 自签名证书，通常不需要客户端证书验证
        # 如果你的安全合规要求必须验证证书链，可以去掉上面这行，或者改成：
        # ssl_ca_certs="/path/to/elasticache-ca-cert.pem"
    )
    return client

def main():
    r = get_redis_client()
    for symbol in symbols:
        # print(f"共有{r.dbsize()}个key")
        # print(f"所有key: {r.keys()}")

        # 修改深度倍数
        #print(f"深度: {r.hgetall('volume_percent')}")
        try:
            res = r.hget('volume_percent', symbol)
            print(f"{symbol}深度: {float(res)} {round(float(res)*rate, 1)}")
        #     #r.hset('volume_percent', symbol, 5)
        except:
            print(f"{symbol}深度倍数不存在")
        #     #r.hset('volume_percent', symbol, 20)
        # #print(f"最新{symbol}深度: {r.hget('volume_percent', symbol)}")
        # continue
        # 在volume_percent里面添加一个key是EURQ-USDT,value是2的数据
        

        # 修改价差百分比
        #print(f"价差: {r.hgetall('price_percent')}")
        try:
           print(f"{symbol}价差: {r.hget('price_percent', symbol)}")
        except:
           print(f"{symbol}价差百分比不存在")
        # r.hset('price_percent', symbol, 0.0025)
        # print(f"{symbol}价差: {r.hget('price_percent', symbol)}")

        # 修改刷量倍数
        symbol = symbol.replace('-USDT', '')
        # print(f"刷量: {r.hgetall('trade_volume_percent')}")
        try:
            diff = r.hget('trade_volume_percent', symbol)
            diff = float(diff)
            #print(f"{symbol}刷量: {diff}")
            # 修改刷量参数(倍数)
            if diff >= 0.2:
            #if diff >= 0.4:
                new_diff = round(diff-0.1, 1)
                print(f"{symbol}刷量: {diff} {type(diff)}")
                #r.hset('trade_volume_percent', symbol, new_diff)
                new = r.hget('trade_volume_percent', symbol)
                print(f"{symbol}刷量: {new}")
        except:
            print(f"{symbol}刷量倍数不存在")
            # 若没有设置,则添加刷量参数
            r.hset('trade_volume_percent', symbol, '2')
        #r.hset('trade_volume_percent', symbol, new_diff)
        #print(f"{symbol}刷量: {r.hget('trade_volume_percent', symbol)}")
    

        # print(f"测试连接是否成功: {r.ping()}")
        # print(f"共有{r.dbsize()}个key")
        # print(f"所有key: {r.keys()}")
        # print(f"指定key的类型: {r.type('HEART_BEAT_TRADE')}")  
        # print(f"指定{symbol}的值: {r.hgetall('HEART_BEAT_TRADE')}")
        # print(f"指定key的field值: {r.hget('HEART_BEAT_TRADE', 'CHILLGUY-USDT|NEAR')}")  # DEFENSE  DEPTH
        # print(f"指定key的field值: {r.hget('HEART_BEAT_TRADE', 'CHILLGUY-USDT|DEPTH')}")
        # print(f"指定key的field值: {r.hget('HEART_BEAT_TRADE', 'CHILLGUY-USDT|DEFENSE')}")
        # print(f"指定key的field值: {r.hget(symbol, 'price')}")
        # print(f"删除指定key: {r.delete(symbol)}")     # 删除某个key
        # print(f"删除指定key的field值: {r.hdel('HEART_BEAT_TRADE', 'CHILLGUY-USDT|NEAR')}")
        # print(f"更新指定key的field值: {r.hset(symbol, 'price', '1000000')}")

if __name__ == "__main__":
    main()

