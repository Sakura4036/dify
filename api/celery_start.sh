cd ~/github/dify/api

source activate dify

export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890

celery -A app.celery worker -P gevent -c 1 -Q dataset,generation,mail,ops_trace --loglevel INFO | tee logs/run_celery_$(date +%y%m%d).log
