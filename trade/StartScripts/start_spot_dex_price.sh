export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_dex_server/price_dex_server.py"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_dex_server/price_dex_server.py >> $CODE_DIR/StartScripts/log/price_dex_server.log  &
