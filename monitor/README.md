### 服务和目录

服务器 ：

```
ssh ubuntu@52.74.21.180
```

目录：

```
cd /home/ubuntu/monitor
```



#### 现货监控：

- 启动：

```
 python manage_quant.py start
```

- 重启：

```
 python manage_quant.py restart
```

- 暂停： 

```
python manage_quant.py stop
```

- 监控文件

```
/home/ubuntu/monitor/spot/spot_acc_precision.py               # 精度监控、价格区间
/home/ubuntu/monitor/spot/spot_acc_gear_depth.py              # 深度监测
/home/ubuntu/monitor/spot/spot_acc_kline.py                   # 5minK线
/home/ubuntu/monitor/spot/spot_acc_updown.py                  # 涨跌服务监控
/home/ubuntu/monitor/spot/abc_user_deposit_withdraw_list.py   # abc充值监控
/home/ubuntu/monitor/spot/spot_acc_precision_price.py         # 界面精度与默认精度
/home/ubuntu/monitor/spot/spot_redis_price.py                 # redis 1、2 号库价格监控
/home/ubuntu/monitor/spot/spot_get_mongoacc_orders.py         # MongoOrders mongodb转存
/home/ubuntu/monitor/spot/spot_high_frequency_trading.py      # 高频交易
/home/ubuntu/monitor/spot/spot_acc_avg_amount_orders.py       # 成交量监控
/home/ubuntu/monitor/spot/spot_get_mongo_user.py              # 现货 交易账户与用户成交
```



#### 合约监控：

>nohup

- 启动：

```
 python manage_contract.py start
```

- 重启： 

```
python manage_contract.py restart
```

- 暂停： 

```
python manage_contract.py stop
```

- 监控文件

```
/home/ubuntu/monitor/contract/con_risk_rate.py                # 仓位监控
/home/ubuntu/monitor/contract/con_gear_depth.py               # 深度监测
/home/ubuntu/monitor/contract/con_capitalrate.py              # 资金费率
/home/ubuntu/monitor/contract/con_precision_price.py          # 价格精度监控
/home/ubuntu/monitor/contract/con_position_user_list.py       # 合约用户持仓监控
/home/ubuntu/monitor/contract/con_get_mongoacc_orders.py      # 合约mongo
/home/ubuntu/monitor/contract/con_high_frequency_trading.py   # 合约高频1小时
/home/ubuntu/monitor/contract/con_orders_profit.py            # 合约盈亏较多
/home/ubuntu/monitor/contract/con_acc_updown.py               # 24小时涨跌幅度
/home/ubuntu/monitor/contract/con_acc_kline.py                # 5min kline涨跌幅度
/home/ubuntu/monitor/contract/con_ex.py                       # 合约对冲账户信息
```



#### 定时任务 ：

> crontab -e

- 现货定时任务

```
0 */1 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_fee.py # 凌晨到当前时间监控
0 */1 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_swap_pool.py # 链上池子监控
1 0 * * *     /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_get_mongo_day.py # mongo数据按天保存
0 */1 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_get_mongo_order.py # 订单成交量监控
3 */1 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/delete_mysql_timeout.py # 删除对冲数据库敞口数据
0 */1 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/correct_abc_asset_gap.py # 转存数据异常丢失监控
*/10 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_get_mongo_wallet.py # 盈亏监控
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_acc_orders_profit.py # 交易用户行为监控
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_exchange_precision.py # 上下线币对监控
*/10 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_get_transferassets.py  # 内部账户划转监控
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_get_swap_block_number.py # 区块高度监控
# 0 */1 * * * /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_high_frequency_trading.py 现货高频套利
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_exchange_update_currency.py # 上下线币对监控
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/spot/spot_exchange_deposit_withdraw.py # 交易所充提
```



- 合约定时任务

```
*/10 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/con_fee.py # 凌晨到当前时间监控
2 */8 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/con_treaty_cost.py  # 合约资金费用
*/10 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/con_wallet_profit.py # 盈亏监控
0 */2 * * *   /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/con_abc_bitget_depth.py # 和bitget对比深度监控
2 10 * * *    /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/con_treaty_cost_time.py # 资金费率计算时间监控
1 0 * * *     /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/contract_get_mongo_day.py # mongo每天数据保存 
*/30 * * * *  /home/ubuntu/miniconda3/envs/monitor/bin/python3.9 /home/ubuntu/monitor/contract/contract_exchange_precision.py # 上下线币对监控

```



### 数据库说明



#### 现货  ｜**db = fund**

- hedge                                             现货盈亏统计=内部(mongo)+外部（资产差值），（盈亏按照同一时间 ： sum(对冲头寸｜U) ）
- hedge_trades_orders                  现货订单盈亏统计 =内部(mongo)+外部(成交记录)。(盈亏按照同一时间 ： sum(对冲头寸｜U) ）

- mongodb_day                               现货按照每天统计用户的盈亏 （统计订单的盈亏需要）

- mongoorders                                mongo数据转存在mysql中（uid一定是用户，Aid是量化账户，一条记录包含用户和量化账户）

- spot_profit_loss_brief                  头天提币，第二天到，临时处理盈亏。

- trades_orders_day                       现货外部对冲成交数据统计，按照每天统计
- exchange_transfer_profit            **<u> 扎帐</u>** 的时候，需要在此处 <u>**手动 **</u>添加一条记录（资产把盈亏提走的时候）
- exchange_deposit_withdraw       dc账户以及外部所有对冲账户的充提情况
- exchange_transfer                          资金不足的时候，从17号账户划转到196账户（该**记录自动添加**，因为现货盈亏统计用的是订单统计，所以量化账户转账到196，一定要记录，不然盈亏会异常）

#### 合约｜**db = fund**

- contract_mongodb_day       按照每天统计用户的盈亏 （统计订单的盈亏需要）

- contract_mongoorders        把mongo数据转存在mysql中（里面含有用户和量化账户的所有交易，分析用户交易行为需要用到）

- contract_profitloss               合约盈亏的统计（盈亏按照同一时间 ： sum(差值) ）
- contract_profitloss_order    按照用户订单统计盈亏 （盈亏按照同一时间 ： sum(盈利) ）

- contract_treaty_cost             abc账户的资金费用统计（内部）

  

#### 现货对冲｜**db = hedge**

- abc_asset_gap          现货内部敞口统计

- external_asset_gap     现货外部敞口统计
- fee_asset_gap          充提手续费统计
这三张表的和，就是hedge表中的对冲池列的数据，表示未对冲的币的数量

- orders                        外部开单
- orders_ws            ws外部开单
- trades                         外部成交
- trades_ws                  ws外部成交
- hedge_config            对冲配置
- dex_orders
- dex_currency_hedge_config      


### 监控⚠️

- 紧急报警                                   紧急程度：⭐️⭐️⭐️⭐️⭐️

  一旦出现报警需要紧急处理。

- 监控-aws                                   紧急程度：⭐️⭐️⭐️⭐️⭐️
  一旦出现报警需要紧急处理。

- heart监控                                  紧急程度：⭐️⭐️⭐️⭐️

  一般脚本断掉，会出现报警

  需要根据报警内容判断。如果是和做市相关的需要紧急联系；如果是监控之类的，紧急程序程度可以缓缓。

- redis价格                                  紧急程度：⭐️⭐️⭐️⭐️
  如果出现：🩸🩸🩸 ，紧急程度提升到最高级别。可能是获取价格失败。
  如果价差出现很大：比如价差达到2%以上，建议排查一下原因，然后处理

- 现货对冲                                   紧急程度：⭐️⭐️⭐️

  <u>**" 资金不够对冲，请联系资产"**</u> 的字样，根据要求联系资产

  <u>**"MATIC对冲超过30min !"**</u> 的字样，需要看一下对冲的参数等

- 手续费、公告、上下线            紧急程度：⭐️⭐️⭐️

  如果出现下线币对，或者上线币对，或者分叉，api升级等和做市相关的，需要及时处理。

- 资金费率监控信息                    紧急程度：⭐️⭐️

  如果出现资金费率偏离很大，可能需要手动调整

- 现货 合约 盈利亏损                  紧急程度：⭐️⭐️

- 其他剩余监控                            紧急程度：⭐️