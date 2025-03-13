cd ~/github/dify/api

source activate dify

nohup flask run --host 0.0.0.0 --port=5001 --debug > logs/run_$(date +%y%m%d).log 2>&1 &
