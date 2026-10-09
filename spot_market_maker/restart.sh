pkill -f 'spot_market_maker/bin/python3.11 manage.py run SERVER='

PYTHON_DIR=/home/ubuntu/miniconda3/envs/spot_market_maker/bin

nohup $PYTHON_DIR/python3.11 manage.py run SERVER=1 &
sleep 1
exec ps aux | grep -E 'manage.py run SERVER='
echo '---------success -----------'
echo 'Logs CMD :'
echo 'tail -f nohup.out'

