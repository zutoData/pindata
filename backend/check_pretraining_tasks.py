#!/usr/bin/env python
"""
预训练数据清洗任务检查脚本
"""

import os
import sys
import time
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_pretraining_tasks():
    """检查预训练数据清洗任务状态"""
    try:
        from app.celery_app import celery
        from app.models import Task as TaskModel, TaskStatus
        from app.db import db
        from app import create_app
        
        # 创建应用上下文
        app = create_app()
        
        with app.app_context():
            print("=" * 60)
            print(f"预训练数据清洗任务检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            # 检查数据库中的任务
            print("\n📊 数据库任务状态:")
            tasks = TaskModel.query.filter(
                TaskModel.name.like('%预训练%')
            ).order_by(TaskModel.created_at.desc()).limit(10).all()
            
            if tasks:
                for task in tasks:
                    status_emoji = {
                        TaskStatus.PENDING: "⏳",
                        TaskStatus.RUNNING: "🟢",
                        TaskStatus.COMPLETED: "✅",
                        TaskStatus.FAILED: "❌"
                    }.get(task.status, "❓")
                    
                    print(f"  {status_emoji} ID: {task.id}")
                    print(f"    名称: {task.name}")
                    print(f"    状态: {task.status.value}")
                    print(f"    进度: {task.progress}%")
                    print(f"    当前文件: {task.current_file or 'N/A'}")
                    print(f"    创建时间: {task.created_at}")
                    if task.started_at:
                        print(f"    开始时间: {task.started_at}")
                    if task.error_message:
                        print(f"    错误信息: {task.error_message}")
                    print(f"    Celery任务ID: {task.celery_task_id}")
                    print("    " + "-" * 50)
            else:
                print("  📝 没有找到预训练数据清洗任务")
            
            # 检查Celery任务状态
            print("\n🔍 Celery任务状态:")
            inspect = celery.control.inspect()
            
            # 获取活跃任务
            active_tasks = inspect.active()
            if active_tasks:
                print("  🟢 活跃任务:")
                for worker, tasks in active_tasks.items():
                    print(f"    Worker: {worker}")
                    for task in tasks:
                        task_id = task.get('id', 'unknown')
                        task_name = task.get('name', 'unknown')
                        start_time = task.get('time_start', 0)
                        
                        if start_time:
                            start_dt = datetime.fromtimestamp(start_time)
                            duration = datetime.now() - start_dt
                            duration_str = str(duration).split('.')[0]
                            
                            print(f"      📋 任务ID: {task_id}")
                            print(f"      📝 任务名称: {task_name}")
                            print(f"      ⏰ 开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"      ⏳ 运行时长: {duration_str}")
                            
                            # 检查是否是卡住的任务
                            if duration > timedelta(hours=1):
                                print(f"      ⚠️  警告: 任务运行时间过长 ({duration_str})")
                            
                            print("      " + "-" * 40)
            else:
                print("  📝 没有活跃任务")
            
            # 检查预留任务
            reserved_tasks = inspect.reserved()
            if reserved_tasks:
                print("\n📋 预留任务:")
                for worker, tasks in reserved_tasks.items():
                    if tasks:
                        print(f"    Worker: {worker}")
                        for task in tasks:
                            print(f"      📋 {task.get('name', 'unknown')} ({task.get('id', 'unknown')})")
            
            # 检查失败任务
            failed_tasks = inspect.failed()
            if failed_tasks:
                print("\n❌ 失败任务:")
                for worker, tasks in failed_tasks.items():
                    if tasks:
                        print(f"    Worker: {worker}")
                        for task in tasks:
                            print(f"      📋 {task.get('name', 'unknown')} ({task.get('id', 'unknown')})")
            
            # 检查Worker统计信息
            stats = inspect.stats()
            if stats:
                print("\n📊 Worker统计:")
                for worker, stat in stats.items():
                    print(f"    Worker: {worker}")
                    print(f"      🔄 处理任务数: {stat.get('total', 0)}")
                    print(f"      📈 并发数: {stat.get('pool', {}).get('max-concurrency', 'unknown')}")
                    print(f"      🕐 运行时间: {stat.get('clock', 'unknown')}")
            
            print("\n" + "=" * 60)
            print("检查完成")
            print("=" * 60)
            
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        print("请确保数据库和Celery服务正在运行")

def kill_stuck_tasks():
    """终止卡住的任务"""
    try:
        from app.celery_app import celery
        
        print("🛑 终止卡住的任务...")
        
        # 获取活跃任务
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    start_time = task.get('time_start', 0)
                    if start_time:
                        start_dt = datetime.fromtimestamp(start_time)
                        duration = datetime.now() - start_dt
                        
                        # 如果任务运行超过2小时，认为是卡住的
                        if duration > timedelta(hours=2):
                            task_id = task.get('id')
                            task_name = task.get('name')
                            print(f"🔪 终止卡住的任务: {task_name} ({task_id})")
                            celery.control.revoke(task_id, terminate=True)
        
        print("✅ 清理完成")
        
    except Exception as e:
        print(f"❌ 清理失败: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'kill':
        kill_stuck_tasks()
    else:
        check_pretraining_tasks() 