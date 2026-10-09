import redis

DB = 7
symbols = ['CHILLGUY-USDT', 'BABYDOGE-USDT', 'GOAT-USDT', 'CORE-USDT', 'TUT-USDT', 'BAN-USDT', 'MEW-USDT', 'MUBARAK-USDT', 'ELX-USDT', 'MELANIA-USDT', 'IDOL-USDT', 'VINE-USDT']

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
    # for symbol in symbols:
    print(f"测试连接是否成功: {r.ping()}")
    print(f"共有{r.dbsize()}个key")
    print(f"所有key: {r.keys()}")
    print(f"指定key的类型: {r.type('HEART_BEAT')}")
    print(f"指定的值: {r.hgetall('HEART_BEAT')}")
    print(f"指定key的field值: {r.hget('HEART_BEAT', '外部交易所维护状态')}")
    # print(f"删除指定key: {r.delete(symbol)}")
    # print(f"更新指定key的field值: {r.hset(symbol, 'price', '1000000')}")
    # deleted = r.hdel('HEART_BEAT', '外部交易所维护状态')
    # if deleted:
    #     print("删除成功")
    # else:
    #     print("该 field 不存在")
    # print(f"指定key的field值: {r.hget('HEART_BEAT', '外部交易所维护状态')}")


if __name__ == "__main__":
    main()