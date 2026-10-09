import redis

DB = [1,3,4,7]
symbols = ['AAVE-USDT','ACT-USDT','AEVO-USDT','ANKR-USDT','AXS-USDT','BEAMX-USDT','BMT-USDT','C-USDT','CHZ-USDT','CRCLON-USDT','CRV-USDT','CSCOON-USDT','EGLD-USDT','ENA-USDT','ERA-USDT','EURQ-USDT','FTT-USDT','GALA-USDT','GIGGLE-USDT','GLM-USDT','GRT-USDT','HOODON-USDT','HYPER-USDT','IAUON-USDT','JASMY-USDT','JUP-USDT','KERNEL-USDT','LDO-USDT','LINK-USDT','LLYON-USDT','LPT-USDT','MANA-USDT','MANTRA-USDT','MASK-USDT','MOVE-USDT','NEWT-USDT','NFLXON-USDT','NXPC-USDT','ONDO-USDT','ORCA-USDT','PENGU-USDT','PEPON-USDT','QNT-USDT','RENDER-USDT','SKY-USDT','SXT-USDT','TIA-USDT','W-USDT']

def get_redis_client(db: int):
    client = redis.Redis(
        host='market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com',        # 你的主节点或配置端点
        port=6379,                        # AWS ElastiCache Redis 默认 TLS 端口就是 6379
        db=db,                            # 必须是 int，不能传 DB 列表
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
    for redis_db in DB:
        r = get_redis_client(redis_db)
        print(f"===== 切换到 db={redis_db} =====")
        for symbol in symbols:
            if redis_db != 7:
                print(f"指定{symbol}的值: {r.hgetall(symbol)}")
                #print(r.hset('auto_wd_signal', 'BTC', '0'))
                print(f"删除指定key: {r.delete(symbol)}")
                #print(r.hgetall("auto_wd_signal"))
            else:
                #print(r.hgetall('HEART_BEAT_TRADE'))
                print(r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEPTH'))
                print(r.hdel('HEART_BEAT_TRADE', f'{symbol}|NEAR'))
                print(r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEFENSE'))
                
                #print(r.hgetall('HEART_BEAT'))
                #print(f"删除: {r.hdel('HEART_BEAT', '外部交易所维护状态')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '外部交易所公告')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '外部交易所充提状态')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '对冲配置优先级检测')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '订单成交量监控')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '对冲阈值监控预警')}")
                # print(f"删除: {r.hdel('HEART_BEAT', '对冲阈值监控预警|订单')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '现货交易')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '现货费用统计')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '对冲与对标交易所一致性')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '各个交易所充提监控')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '自动化充提-sync-status')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '自动化充提-main-process')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '合约资金费用')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '合约涨跌服务监控')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '价格服务')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '刷量')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '现货做市')}")
                #print(f"删除: {r.hdel('HEART_BEAT', '合约风险率')}")

                #print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|NEAR')}")
                #print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|DEPTH')}")
                #print(f"指定{symbol}的field值: {r.hget('HEART_BEAT_TRADE', f'{symbol}|DEFENSE')}")
                #print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|NEAR')}")
                #print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEPTH')}")
                #print(f"删除指定{symbol}的field值: {r.hdel('HEART_BEAT_TRADE', f'{symbol}|DEFENSE')}")
            
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

