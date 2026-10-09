pkill -f 'spot_paddington/bin/python3.11 launcher_ws.py'

PYTHON_DIR=/home/ubuntu/miniconda3/envs/spot_paddington/bin

nohup $PYTHON_DIR/python3.11 launcher_ws.py >> ws_nohup.out &
sleep 1
exec ps aux | grep -E 'spot_paddington'
echo '---------success -----------'

