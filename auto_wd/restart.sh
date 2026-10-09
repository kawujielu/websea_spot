
export PYTHONPATH=..
pkill -f 'spot_paddington/bin/python3.11 /home/ubuntu/code/spot_paddington/auto_wd/wd.py'

PYTHON_DIR=/home/ubuntu/miniconda3/envs/spot_paddington/bin

nohup $PYTHON_DIR/python3.11 /home/ubuntu/code/spot_paddington/auto_wd/wd.py >> /home/ubuntu/code/spot_paddington/auto_wd/nohup.out &


