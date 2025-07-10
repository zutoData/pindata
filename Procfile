backend: CONDA_PATH=$(conda info --base); cd backend && $CONDA_PATH/envs/pindata-env/bin/python run.py
celery_default: CONDA_PATH=$(conda info --base); cd backend && $CONDA_PATH/envs/pindata-env/bin/celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4 -n worker_default@%h -Q celery
celery_long: CONDA_PATH=$(conda info --base); cd backend && $CONDA_PATH/envs/pindata-env/bin/celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=2 -n worker_long@%h -Q long_running
celery_conversion: CONDA_PATH=$(conda info --base); cd backend && $CONDA_PATH/envs/pindata-env/bin/celery -A celery_worker.celery worker --loglevel=info --pool=threads --concurrency=4 -n worker_conversion@%h -Q conversion
frontend: cd frontend && pnpm run dev 