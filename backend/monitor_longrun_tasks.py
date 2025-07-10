#!/usr/bin/env python
"""
长时间运行任务监控脚本
用于监控数据抽取等长时间运行的Celery任务
"""

import os
import sys
import time
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def monitor_tasks():
    """监控长时间运行的任务"""
    try:
        from app.celery_app import celery
        
        print("=" * 60)
        print(f"长时间任务监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # 获取活跃任务
        inspect = celery.control.inspect()
        
        # 获取活跃任务
        active_tasks = inspect.active()
        if active_tasks:
            print("🟢 当前活跃任务:")
            for worker, tasks in active_tasks.items():
                print(f"\n Worker: {worker}")
                for task in tasks:
                    task_id = task.get('id', 'unknown')
                    task_name = task.get('name', 'unknown')
                    start_time = task.get('time_start', 0)
                    
                    if start_time:
                        start_dt = datetime.fromtimestamp(start_time)
                        duration = datetime.now() - start_dt
                        duration_str = str(duration).split('.')[0]  # 去掉微秒
                        
                        print(f"  📋 任务ID: {task_id}")
                        print(f"  📝 任务名称: {task_name}")
                        print(f"  ⏰ 开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"  ⏳ 运行时长: {duration_str}")
                        print(f"  📊 参数: {task.get('args', [])}")
                        print("  " + "-" * 50)
        else:
            print("🔴 没有活跃的任务")
        
        # 获取已注册任务
        registered_tasks = inspect.registered()
        if registered_tasks:
            print("\n📋 已注册任务:")
            for worker, tasks in registered_tasks.items():
                print(f"\n Worker: {worker}")
                for task in tasks:
                    if 'dataset' in task.lower() or 'generation' in task.lower():
                        print(f"  ✅ {task}")
        
        # 获取Worker统计信息
        stats = inspect.stats()
        if stats:
            print("\n📊 Worker 统计信息:")
            for worker, stat in stats.items():
                print(f"\n Worker: {worker}")
                print(f"  🔄 处理任务数: {stat.get('total', 0)}")
                print(f"  📈 连接池: {stat.get('pool', {}).get('max-concurrency', 'unknown')}")
                print(f"  🕐 运行时间: {stat.get('clock', 'unknown')}")
        
        # 获取预留任务
        reserved_tasks = inspect.reserved()
        if reserved_tasks:
            print("\n�� 预留任务:")
            for worker, tasks in reserved_tasks.items():
                if tasks:
                    print(f"\n Worker: {worker}")
                    for task in tasks:
                        print(f"  📋 {task.get('name', 'unknown')} ({task.get('id', 'unknown')})")
        
        print("\n" + "=" * 60)
        print("监控完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 监控失败: {str(e)}")
        print("请确保 Celery Worker 正在运行")

def continuous_monitor(interval=30):
    """持续监控模式"""
    print(f"开始持续监控模式，每 {interval} 秒刷新一次...")
    print("按 Ctrl+C 停止监控")
    
    try:
        while True:
            monitor_tasks()
            print(f"\n⏰ 等待 {interval} 秒后刷新...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n监控已停止")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='长时间任务监控')
    parser.add_argument('--continuous', '-c', action='store_true', 
                       help='持续监控模式')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='刷新间隔（秒），默认30秒')
    
    args = parser.parse_args()
    
    if args.continuous:
        continuous_monitor(args.interval)
    else:
        monitor_tasks()
