cd ~/github/dify/api

source activate dify

export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890

uv run flask run --host 0.0.0.0 --port=5001 --debug | tee logs/run_$(date +%y%m%d).log
