cd ~/github/dify/api

source activate dify

nohup celery -A app.celery worker -P gevent -c 1 -Q dataset,generation,mail --loglevel INFO > logs/run_celery_$(date +%y%m%d).log 2>&1 &
