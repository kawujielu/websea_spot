export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_contract/contract_price_from_contract_ask_bid.py"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_contract/contract_price_from_contract_ask_bid.py >> $CODE_DIR/StartScripts/log/contract_price_from_contract_ask_bid.log  &
