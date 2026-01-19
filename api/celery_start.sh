cd ~/github/dify/api

source activate dify

#export http_proxy=http://127.0.0.1:7890
#export https_proxy=http://127.0.0.1:7890

uv run celery -A app.celery worker -P gevent -c 1 --loglevel INFO -Q dataset,priority_dataset,priority_pipeline,pipeline,mail,ops_trace,app_deletion,plugin,workflow_storage,conversation,workflow,schedule_poller,schedule_executor,triggered_workflow_dispatcher,trigger_refresh_executor --loglevel INFO | tee logs/run_celery_$(date +%y%m%d).log
