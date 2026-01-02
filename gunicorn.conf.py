"""
Gunicorn configuration for production Django deployment.
Optimized for performance, security, and reliability.
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to prevent memory leaks
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 50))

# Memory management - restart workers if they exceed memory limits
# This helps prevent OOM kills in production
worker_memory_limit = int(os.environ.get("GUNICORN_WORKER_MEMORY_LIMIT", 512 * 1024 * 1024))  # 512MB default

# Preload application for better performance
preload_app = True

# Security
user = None  # Run as the user specified in Dockerfile (django)
group = None
tmp_upload_dir = None

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "faq-django-app"

# Server mechanics
daemon = False
pidfile = None
umask = 0
tmp_upload_dir = None

# SSL (if certificates are provided)
keyfile = os.environ.get("SSL_KEYFILE")
certfile = os.environ.get("SSL_CERTFILE")

# Worker process lifecycle
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Gunicorn server...")
    server.log.info("Configuration: %d workers, preload_app=%s, worker_class=%s", 
                    server.cfg.workers, server.cfg.preload_app, server.cfg.worker_class)
    server.log.info("Memory limit per worker: %d MB", 
                    worker_memory_limit / 1024 / 1024 if 'worker_memory_limit' in globals() else 512)

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Gunicorn server...")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Gunicorn server is ready. Listening on: %s", server.address)
    server.log.info("Health check endpoint available at: http://%s/health/", server.address[0] + ":" + str(server.address[1]) if isinstance(server.address, tuple) else server.address)
    server.log.info("Server ready to handle requests with %d workers", server.cfg.workers)

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.debug("Worker %s is being forked", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.debug("Worker %s forked", worker.pid)

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.debug("Worker %s initialized", worker.pid)
    
    # Set up memory monitoring if psutil is available
    try:
        import psutil
        process = psutil.Process()
        worker.log.info("Worker %s memory usage: %.2f MB", 
                       worker.pid, process.memory_info().rss / 1024 / 1024)
    except ImportError:
        pass

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker %s aborted", worker.pid)
    
    # Log memory usage if available
    try:
        import psutil
        process = psutil.Process()
        worker.log.warning("Worker %s aborted with memory usage: %.2f MB", 
                          worker.pid, process.memory_info().rss / 1024 / 1024)
    except ImportError:
        pass

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug("%s %s", req.method, req.uri)

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass

def child_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    server.log.info("Worker %s exited", worker.pid)

def worker_exit(server, worker):
    """Called just after a worker has been exited, in the worker process."""
    worker.log.info("Worker %s exiting", worker.pid)

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    server.log.info("Number of workers changed from %s to %s", old_value, new_value)

def on_exit(server):
    """Called just before exiting."""
    server.log.info("Shutting down Gunicorn server...")
    server.log.info("Graceful shutdown completed")

# Memory and resource limits
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance tuning
worker_tmp_dir = "/dev/shm"  # Use shared memory for better performance
forwarded_allow_ips = "*"    # Trust proxy headers (configure appropriately for your setup)
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Health check configuration
# Gunicorn will respond to health checks on the main application port
# The Django application should have a /health/ endpoint for this purpose