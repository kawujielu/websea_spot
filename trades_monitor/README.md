开发：
 git clone ssh://git-codecommit.ap-southeast-1.amazonaws.com/v1/repos/trades_monitor

服务器位置： 52.74.21.180

#### 定时脚本
```
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/withdraw_exchange_async.py >> /home/ubuntu/whm/log/withdraw_exchange.log
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/withdraw_exchange_fee_async.py >> /home/ubuntu/whm/log/withdraw_exchange_fee.log
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/exchange_symbols.py >> /home/ubuntu/whm/log/exchange_symbols.log
*/10 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/exchange_status.py >> /home/ubuntu/whm/log/exchange_status.log
*/5 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/check_redis_price.py >> /home/ubuntu/whm/log/check_redis.log
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/check_pair_exchange_async.py >> /home/ubuntu/whm/log/check_pair_exchange.log
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/withdraw_deposit_monitor_async.py >> /home/ubuntu/whm/log/withdraw_deposit_monitor.log
*/10 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/check_hedge_config.py >> /home/ubuntu/whm/log/check_hedge_config.log
*/10 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/redis_precision.py >> /home/ubuntu/whm/log/redis_precision.log
*/10 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/check_libs_config.py >> /home/ubuntu/whm/log/check_libs_config.log
*/30 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/record_margin_db.py >> /home/ubuntu/whm/log/record_margin_db.log
0 */1 * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/check_hedge_exchange_fee.py >> /home/ubuntu/whm/log/check_hedge_exchange_fee.log
# 定时清理/tmp 缓存
5 12 * * * /usr/bin/sh /home/ubuntu/whm/trades_monitor/monitor_spot/clear_chrom.sh
0 12 * * * /bin/rm -rf /tmp/.com.google.Chrome.*
*/15 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_contract/contract_exchange_symbols.py >> /home/ubuntu/whm/log/contract_exchange_symbols.log
0 */3 * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_contract/check_contract_exchange_async.py >> /home/ubuntu/whm/log/check_contract_exchange.log
*/10 * * * * /home/ubuntu/miniconda3/bin/python3 /home/ubuntu/whm/trades_monitor/monitor_spot/loan_margin_borrow.py >> /home/ubuntu/whm/log/loan_margin_borrow.log
```