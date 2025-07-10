#!/usr/bin/env python
"""
强力任务清理脚本
用于彻底清理卡住的任务，包括强制终止Celery任务和清理数据库状态
"""

import os
import sys
import signal
import subprocess
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def kill_celery_workers():
    """强制终止所有Celery worker进程"""
    try:
        print("🔪 强制终止所有Celery worker进程...")
        
        # 查找所有Celery相关进程
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        celery_pids = []
        for line in lines:
            if 'celery' in line and 'worker' in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    celery_pids.append(pid)
                    print(f"  发现Celery进程: PID {pid}")
        
        # 强制终止进程
        for pid in celery_pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                print(f"  ✅ 已终止进程: PID {pid}")
            except Exception as e:
                print(f"  ❌ 无法终止进程 {pid}: {str(e)}")
        
        if celery_pids:
            print(f"✅ 共终止了 {len(celery_pids)} 个Celery进程")
        else:
            print("✅ 未发现运行中的Celery进程")
        
    except Exception as e:
        print(f"❌ 终止Celery进程失败: {str(e)}")

def force_revoke_all_tasks():
    """强制撤销所有Celery任务"""
    try:
        from app.celery_app import celery
        
        print("🛑 强制撤销所有Celery任务...")
        
        # 获取活跃任务
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        
        if active_tasks:
            all_task_ids = []
            for worker, tasks in active_tasks.items():
                print(f"  Worker: {worker}")
                for task in tasks:
                    task_id = task.get('id')
                    task_name = task.get('name', 'unknown')
                    print(f"    任务: {task_name} - {task_id}")
                    all_task_ids.append(task_id)
            
            if all_task_ids:
                # 批量撤销
                celery.control.revoke(all_task_ids, terminate=True, signal='SIGKILL')
                print(f"  ✅ 已撤销 {len(all_task_ids)} 个任务")
            else:
                print("  ✅ 没有活跃任务需要撤销")
        else:
            print("  ✅ 没有活跃任务")
            
    except Exception as e:
        print(f"❌ 撤销任务失败: {str(e)}")

def cleanup_database_tasks():
    """清理数据库中的任务状态"""
    try:
        from app import create_app
        from app.models import Task, TaskStatus
        from app.db import db
        
        app = create_app()
        
        with app.app_context():
            print("🗄️ 清理数据库任务状态...")
            
            # 查找所有运行中或等待中的任务
            running_tasks = Task.query.filter(
                Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
            ).all()
            
            if running_tasks:
                print(f"  发现 {len(running_tasks)} 个需要清理的任务:")
                
                for task in running_tasks:
                    print(f"    任务: {task.name} - {task.id} - {task.status.value}")
                    
                    # 强制设置为取消状态
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.utcnow()
                    task.error_message = "任务被强制清理"
                
                db.session.commit()
                print(f"  ✅ 已清理 {len(running_tasks)} 个任务")
            else:
                print("  ✅ 没有需要清理的任务")
                
    except Exception as e:
        print(f"❌ 清理数据库任务失败: {str(e)}")

def clear_redis_queues():
    """清理Redis队列"""
    try:
        import redis
        from config.config import Config
        
        print("🧹 清理Redis队列...")
        
        # 连接Redis
        redis_client = redis.from_url(Config.CELERY_BROKER_URL)
        
        # 清理常见的Celery队列
        queues = ['celery', 'long_running', 'conversion', 'default']
        
        for queue in queues:
            try:
                # 清理队列
                redis_client.delete(queue)
                print(f"  ✅ 已清理队列: {queue}")
            except Exception as e:
                print(f"  ❌ 清理队列 {queue} 失败: {str(e)}")
        
        # 清理Celery结果
        try:
            # 获取所有Celery结果键
            keys = redis_client.keys('celery-task-meta-*')
            if keys:
                redis_client.delete(*keys)
                print(f"  ✅ 已清理 {len(keys)} 个任务结果")
            else:
                print("  ✅ 没有需要清理的任务结果")
        except Exception as e:
            print(f"  ❌ 清理任务结果失败: {str(e)}")
            
    except Exception as e:
        print(f"❌ 清理Redis队列失败: {str(e)}")

def check_system_status():
    """检查系统状态"""
    try:
        from app.celery_app import celery
        
        print("📊 检查系统状态...")
        
        # 检查Celery连接
        try:
            inspect = celery.control.inspect()
            stats = inspect.stats()
            if stats:
                print("  ✅ Celery连接正常")
                for worker, stat in stats.items():
                    print(f"    Worker: {worker} - 活跃")
            else:
                print("  ❌ 没有活跃的Celery worker")
        except Exception as e:
            print(f"  ❌ Celery连接失败: {str(e)}")
        
        # 检查Redis连接
        try:
            import redis
            from config.config import Config
            redis_client = redis.from_url(Config.CELERY_BROKER_URL)
            redis_client.ping()
            print("  ✅ Redis连接正常")
        except Exception as e:
            print(f"  ❌ Redis连接失败: {str(e)}")
            
    except Exception as e:
        print(f"❌ 检查系统状态失败: {str(e)}")

def main():
    """主函数"""
    print("=" * 60)
    print("🚨 强力任务清理脚本")
    print("=" * 60)
    print("⚠️  警告: 此脚本将强制终止所有Celery任务和进程!")
    print("⚠️  请确保没有重要任务正在运行!")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--force':
            proceed = True
        elif sys.argv[1] == '--status':
            check_system_status()
            return
        else:
            print("用法:")
            print("  python force_kill_tasks.py --force   # 强制清理所有任务")
            print("  python force_kill_tasks.py --status  # 检查系统状态")
            return
    else:
        response = input("确定要继续吗? (输入 'yes' 确认): ")
        proceed = response.lower() == 'yes'
    
    if not proceed:
        print("❌ 操作已取消")
        return
    
    print("\n🚀 开始清理...")
    
    # 步骤1: 强制撤销所有任务
    force_revoke_all_tasks()
    
    # 步骤2: 强制终止Celery进程
    kill_celery_workers()
    
    # 步骤3: 清理数据库状态
    cleanup_database_tasks()
    
    # 步骤4: 清理Redis队列
    clear_redis_queues()
    
    # 步骤5: 检查系统状态
    print("\n📊 清理完成，检查系统状态...")
    check_system_status()
    
    print("\n" + "=" * 60)
    print("✅ 清理完成!")
    print("💡 建议:")
    print("  1. 重启Celery worker: ./start_celery.sh")
    print("  2. 检查任务状态: python monitor_long_tasks.py")
    print("  3. 如果问题仍然存在，请重启整个系统")
    print("=" * 60)

if __name__ == '__main__':
    main() 