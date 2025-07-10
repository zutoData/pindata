#!/bin/bash

# 启动 Celery Worker 脚本 - 长时间运行版本
# 适用于数据抽取等需要长时间运行的任务

echo "Starting Celery Worker for long-running tasks..."

# 设置环境变量
export FLASK_APP=run.py
export FLASK_ENV=development

# macOS 兼容性设置
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 检查 Redis 连接
echo "Checking Redis connection..."
if redis-cli -h localhost -p 16379 ping > /dev/null 2>&1; then
    echo "✅ Redis 连接正常"
else
    echo "❌ Redis 连接失败，请检查 Redis 服务状态"
    exit 1
fi

echo "Starting Celery Worker for long-running tasks..."
echo "配置说明："
echo "- 无时间限制 (适用于长时间数据抽取)"
echo "- 无任务数限制 (worker 不会自动重启)"
echo "- 较低的并发数 (避免资源竞争)"
echo "- 优化的预取设置 (减少内存使用)"

# 启动 Celery Worker - 长时间运行配置
# --concurrency=2: 降低并发数，减少资源竞争
# --prefetch-multiplier=1: 每个worker只预取1个任务
# --without-gossip: 禁用gossip协议减少网络开销
# --without-mingle: 禁用mingle减少启动时间
# --autoscale=4,1: 自动扩缩容，最多4个进程，最少1个
exec celery -A celery_worker.celery worker \
    --loglevel=info \
    --concurrency=2 \
    -n longrun_worker@%h \
    --without-gossip \
    --without-mingle \
    --prefetch-multiplier=1 \
    --optimization=fair
