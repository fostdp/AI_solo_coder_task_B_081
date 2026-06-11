import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
workers = min(workers, 8)

worker_class = os.getenv("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", 1000))

keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 60))
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

backlog = int(os.getenv("GUNICORN_BACKLOG", 2048))

accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)ss'

preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))
