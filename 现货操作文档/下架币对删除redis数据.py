import redis

DB = [1,3,4,7]
symbols = ['ESP-USDT','APE-USDT','PENDLE-USDT','PUMP-USDT','GMT-USDT','IOTX-USDT','BAT-USDT','NEIRO-USDT','RAY-USDT','SAFE-USDT','FET-USDT','BOME-USDT','YGG-USDT','PEOPLE-USDT']

def get_redis_client(db_num):
    client = redis.Redis(
        host='market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com',        # 你的主节点或配置端点
        port=6379,                        # AWS ElastiCache Redis 默认 TLS 端口就是 6379
        db=db_num,
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
    for db in DB:
        r = get_redis_client(db)
        for symbol in symbols:
            if DB != 7:
                print(f"指定{symbol}的值: {r.hgetall(symbol)}")
                print(f"删除指定key: {r.delete(symbol)}")
            else:
                # print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|NEAR')}")
                # print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|DEPTH')}")
                # print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|DEFENSE')}")
                print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|NEAR')}")
                print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEPTH')}")
                print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEFENSE')}")
            
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