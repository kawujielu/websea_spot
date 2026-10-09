export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_volume_maker/volume_maker_ws_source.py"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_volume_maker/volume_maker_ws_source.py >> $CODE_DIR/StartScripts/log/volume_maker_ws_source.log &
