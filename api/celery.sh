#!/bin/bash
source /home/anvar/my_bot/venv/bin/activate
while pgrep "uvicorn" > /dev/null; do
  sleep 1
done
cd /home/anvar/my_bot/api
celery -A tasks worker --concurrency=1 --loglevel=info
