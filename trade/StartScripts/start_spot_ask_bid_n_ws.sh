export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_spot_price_server/spot_ask_bid_center.py run bn"
pkill -f "launcher_spot_price_server/spot_ask_bid_center.py run hb,okex,gate,mxc,bitget,kraken"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_spot_price_server/spot_ask_bid_center.py run bn >> $CODE_DIR/StartScripts/log/spot_ask_bid_center_1.log  &
nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_spot_price_server/spot_ask_bid_center.py run hb,okex,gate,mxc,bitget,kraken >> $CODE_DIR/StartScripts/log/spot_ask_bid_center_2.log &
