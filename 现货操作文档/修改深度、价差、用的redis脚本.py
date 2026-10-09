import redis

DB =15
symbols = ['BTC-USDT']  #, 'USDQ-USDT', 'EURR-USDT', 'USDR-USDT']

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
        # print(f"深度: {r.hgetall('volume_percent')}")
        try:
            print(f"{symbol}深度: {r.hget('volume_percent', symbol)}")
        except:
            print(f"{symbol}深度倍数不存在")
        # 在volume_percent里面添加一个key是EURQ-USDT,value是2的数据
        # r.hset('volume_percent', symbol, 5)
        # print(f"{symbol}深度: {r.hget('volume_percent', symbol)}")

        # 修改价差百分比
        # print(f"价差: {r.hgetall('price_percent')}")
        try:
            print(f"{symbol}价差: {r.hget('price_percent', symbol)}")
        except:
            print(f"{symbol}价差百分比不存在")
        # r.hset('price_percent', symbol, 0.003)
        # print(f"{symbol}价差: {r.hget('price_percent', symbol)}")

        # 修改刷量倍数
        symbol = symbol.replace('-USDT', '')
        # print(f"刷量: {r.hgetall('trade_volume_percent')}")
        try:
            print(f"{symbol}刷量: {r.hget('trade_volume_percent', symbol)}")
        except:
            print(f"{symbol}刷量倍数不存在")
        # r.hset('trade_volume_percent', symbol, 0.04)
        # print(f"{symbol}刷量: {r.hget('trade_volume_percent', symbol)}")
    

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