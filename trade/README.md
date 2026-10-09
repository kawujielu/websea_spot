### trade 要点
1. 防御数量，如果level大于某个等级，当盘口买卖一小于4个精度会认为有人逼单
2. trading工程中所有服务都在一个工程中所以错误信息保存只在其中一个进程消费，如果这些服务器中有拆分到其他服务器的需要在某一个进程中添加一个
错误消息消费。 send_error_msg
3. 
### ubuntu系统
1. ubuntu 账号通过sudo su切换到root账号 或者 sudo passwd修改root账号密码使用root权限 或者 sudo command使用
2. sudo apt install net-tools  安装ifconfig命令，使得代码中的判断线上还是测试环境的服务器
3. 复制已有系统的.ssh文件夹到新服务器，包括公用私钥公钥以及aws codecommit config
4. aws ec2 绑定公网ip和内网ip
5. 修改配置提高用户的系统打开文件数限制：
vi /etc/security/limits.conf
root或者*表示所有用户 soft nofile 8192
root或者*表示所有用户 hard nofile 8192
查看某个进程目前打开的句柄数量
lsof -p 进程ID|wc -l
检测tcp连接数
lsof -p 8382 | grep TCP | wc -l
查看当前进程设置的最大limits
cat /proc/进程ID/limits
netstat -nat|awk '{print awk $NF}'|sort|uniq -c|sort -n

6. /dev/shm 默认是物理内存的一半大小，映射在内存，用于优化和加速应用跟系统的交互，比如日志落盘前在此缓存，所以如果这个空间被占满，
会导致日志无法写入的问题

### Python环境
requests版本2.30.1 版本问题可能导致ssl验证问题，使用2.28.1

1. 安装依赖gcc等
sudo apt update 
sudo apt-get install build-essential libssl-dev libffi-dev libxml2 libxml2-dev libxslt1-dev zlib1g-dev

2. virtualenv 方式安装 
sudo apt install python3.11
apt-get install python3.11-dev
sudo apt install python3.11-venv

python3.11 -m pip install
python3.11 -m venv virtualenv/trade

3. conda 安装使用
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
conda config --set auto_activate_base false

conda create -n envname python=3.11
conda activate envname
conda deactivate
conda env list
conda remove -n envname --all  # 一般情况不要乱删
conda env export > environment.yaml        # 导出
conda env create -f environment.yaml       # 导入
conda create -n envname2 --clone envname1  # 克隆

4. 共享内存监控
刷量：share_v_m_s
from UltraDict import UltraDict
v = UltraDict(name='share_v_m_s', auto_unlink=False, buffer_size=10_000)

### 特殊安装
aiohttp加速包：aiodns faust-cchardet
redis加速包：hiredis
eventloop uvloop
atomics
pip install -i https://pypi.python.org/simple/ load-remote==3.3
web3 @ git+https://github.com/ethereum/web3.py.git@d7861014f1628496d96c1777dfbedd56bd2fb591
aredis @ git+https://github.com/truekonrads/aredis.git@3f9b65cc3ec63870750b3f16411a5cebec1e9c12

### 下架现货流程
需要在合约配置中配置刷量对标


### 其他服务
1 aws redis
本地6379端口通过aws服务器访问redis实例
ssh -f -N -L6379:market-price-1.sg6zxz.ng.0001.apse1.cache.amazonaws.com:6379 ubuntu@13.228.xxx.xx
本地通过访问本地6379端口访问aws redis
redis-cli -h 127.0.0.1 --tls -p 6379 -a 'A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA'

# aiohttp 
1 使用http1.0默认不使用长连接
self.session[session_name] = aiohttp.ClientSession(version = aiohttp.http.HttpVersion10, base_url=self.contract_host, timeout=3, connector=connector)
2 enable_cleanup_closed 清理ssl未被服务器正常关闭的情况
connector = aiohttp.TCPConnector(limit=self.limit, ssl=self.sslcontext, ttl_dns_cache=10 * 60, keepalive_timeout=60, enable_cleanup_closed=True)
3 服务端nginx是否设置keepalive timeout太短，导致链接被reuse时出现异常