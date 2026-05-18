# gunicorn.conf.py — Configuração para alta concorrência (Render Standard)
import multiprocessing

# Gevent: worker assíncrono — suporta centenas de conexões simultâneas
# com 1 só processo, sem travar em I/O (banco, email, sharepoint)
worker_class = "gevent"
workers = 2                    # 2 workers gevent = centenas de conexões paralelas
worker_connections = 500       # conexões simultâneas por worker

# Timeouts
timeout = 60                   # requests devem responder em 60s
graceful_timeout = 30
keepalive = 10                 # mantém HTTP keepalive por 10s

# Performance
max_requests = 1000            # recicla worker após 1000 requests (evita memory leak)
max_requests_jitter = 100      # evita todos reciclarem ao mesmo tempo

# Bind
bind = "0.0.0.0:10000"

# Logging — só erros em produção
accesslog = "-"
errorlog  = "-"
loglevel  = "warning"

# Preload: carrega o app 1x, compartilhado (economiza memória e tempo de startup)
preload_app = True
