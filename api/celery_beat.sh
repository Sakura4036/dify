cd ~/github/dify/api

source activate dify

#export http_proxy=http://127.0.0.1:7890
#export https_proxy=http://127.0.0.1:7890

uv run celery -A app.celery beat --loglevel INFO | tee logs/run_celery_beat_$(date +%y%m%d).log
