# gunicorn.conf.py — Configuração de performance para Rezende NewRH
import multiprocessing

# Workers: 2-4 para plano free do Render (1 vCPU)
# Fórmula: (2 x CPUs) + 1, mínimo 2
workers = 2
worker_class = "sync"

# Timeouts
timeout = 120          # requests pesados (export Excel, chart_stats)
graceful_timeout = 30
keepalive = 5          # mantém conexão HTTP aberta por 5s (reduz overhead)

# Performance
worker_connections = 100
max_requests = 500     # recicla worker após 500 requests (evita memory leak)
max_requests_jitter = 50  # evita todos reciclarem ao mesmo tempo

# Bind
bind = "0.0.0.0:10000"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "warning"   # só erros em produção (info é muito verboso)

# Preload app (carrega o código 1x, compartilhado entre workers)
preload_app = True
