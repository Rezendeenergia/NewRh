# gunicorn.conf.py — Alta concorrência com gevent + pg8000 compatível
from gevent import monkey
monkey.patch_all()  # deve rodar ANTES de qualquer import de rede/ssl

import multiprocessing

worker_class = "gevent"
workers = 2
worker_connections = 500

timeout = 60
graceful_timeout = 30
keepalive = 10

max_requests = 1000
max_requests_jitter = 100

bind = "0.0.0.0:10000"

accesslog = "-"
errorlog  = "-"
loglevel  = "warning"

preload_app = True
