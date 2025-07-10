#!/bin/bash

# 启动 Celery Worker 脚本 - 优化版本

echo "Starting Celery Worker..."

# 设置环境变量
export FLASK_APP=run.py
export FLASK_ENV=development

# macOS 兼容性设置
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 检查 Redis 连接
echo "Checking Redis connection..."
redis-cli -h localhost -p 16379 ping || {
    echo "Warning: Redis connection failed. Celery may experience issues."
}

echo "Starting Celery Worker with standard configuration..."
echo "注意：此版本适用于普通任务，长时间任务请使用 start_celery_longrun.sh"

# 启动 Celery Worker
# -A: 指定 Celery 应用
# -l: 日志级别
# -c: 并发数（worker 进程数）
# -n: worker 名称
# --without-gossip: 禁用 gossip 协议（减少网络开销）
# --without-mingle: 禁用 mingle（减少启动时间）
# --max-tasks-per-child: 限制每个子进程的任务数
# --prefetch-multiplier: 预取倍数
exec celery -A celery_worker.celery worker \
    --loglevel=info \
    --concurrency=4 \
    -n worker@%h \
    --without-gossip \
    --without-mingle \
    --max-tasks-per-child=1000 \
    --prefetch-multiplier=1 