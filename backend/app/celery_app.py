from celery import Celery
from config.config import Config

def make_celery(app_name=__name__):
    """创建并配置Celery实例"""
    celery = Celery(app_name)
    
    # 使用新的配置格式
    celery.conf.update(
        # Broker 和 Backend 配置
        broker_url=Config.CELERY_BROKER_URL,
        result_backend=Config.CELERY_RESULT_BACKEND,
        
        # Redis 连接配置优化
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        broker_pool_limit=10,
        broker_heartbeat=30,
        broker_heartbeat_checkrate=2.0,
        
        # Redis 连接池配置
        redis_socket_keepalive=True,
        redis_socket_keepalive_options={
            'TCP_KEEPIDLE': 1,
            'TCP_KEEPINTVL': 3,
            'TCP_KEEPCNT': 5,
        },
        redis_retry_on_timeout=True,
        redis_socket_timeout=5.0,
        redis_socket_connect_timeout=5.0,
        
        # Result backend 配置优化
        result_backend_always_retry=True,
        result_backend_retry_on_timeout=True,
        result_backend_max_retries=10,
        result_expires=3600,  # 1小时后过期
        result_cache_max=1000,
        
        # 序列化配置
        task_serializer=getattr(Config, 'CELERY_TASK_SERIALIZER', 'json'),
        accept_content=getattr(Config, 'CELERY_ACCEPT_CONTENT', ['json']),
        result_serializer=getattr(Config, 'CELERY_RESULT_SERIALIZER', 'json'),
        
        # 时区配置
        timezone=getattr(Config, 'CELERY_TIMEZONE', 'UTC'),
        enable_utc=getattr(Config, 'CELERY_ENABLE_UTC', True),
        
        # 任务配置
        task_track_started=True,
        task_time_limit=None,  # 无时间限制，适用于长时间数据抽取任务
        task_soft_time_limit=None,  # 无软时间限制
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
        
        # Worker 配置 - 优化长时间任务
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=None,  # 不限制任务数，避免长时间任务中途重启
        worker_disable_rate_limits=True,
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # 监控配置
        task_send_sent_event=True,
        worker_send_task_events=True,
        
        # 自动发现任务
        include=[
            'app.tasks.conversion_tasks',
            'app.tasks.dataset_import_tasks', 
            'app.tasks.dataset_generation_tasks',
            'app.tasks.dataflow_tasks',  # 添加DataFlow任务
            'app.tasks.chinese_dataflow_tasks'  # 添加中文DataFlow任务
            # 'app.tasks.multimodal_dataset_tasks'  # 暂时移除，功能开发中
        ]
    )
    
    return celery

# 创建全局Celery实例
celery = make_celery('pindata_celery') 