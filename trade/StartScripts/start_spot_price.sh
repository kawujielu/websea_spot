export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_spot_price_server/spot_price.py"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_spot_price_server/spot_price.py >> $CODE_DIR/StartScripts/log/spot_price.log  &
