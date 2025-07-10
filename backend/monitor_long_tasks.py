#!/usr/bin/env python
"""
长时间运行任务监控脚本
专门用于监控数据蒸馏、预训练数据清洗等长时间任务
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        return f"{seconds/60:.1f}分钟"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}小时"
    else:
        return f"{seconds/86400:.1f}天"

def get_task_progress_from_logs(task_id: str) -> Dict:
    """从日志中分析任务进度"""
    try:
        # 这里可以实现日志解析逻辑
        # 暂时返回模拟数据
        return {
            'current_block': 'Unknown',
            'total_blocks': 'Unknown',
            'success_rate': 'Unknown',
            'estimated_remaining': 'Unknown'
        }
    except Exception as e:
        return {'error': str(e)}

def monitor_long_tasks():
    """监控长时间运行的任务"""
    try:
        from app.celery_app import celery
        from app.models import Task as TaskModel, TaskStatus
        from app.db import db
        from app import create_app
        
        # 创建应用上下文
        app = create_app()
        
        with app.app_context():
            print("=" * 80)
            print(f"📊 长时间任务监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 80)
            
            # 检查Celery活跃任务
            print("\n🔄 Celery活跃任务:")
            try:
                active_tasks = celery.control.inspect().active()
                if active_tasks:
                    for worker, tasks in active_tasks.items():
                        if tasks:
                            print(f"\n📍 Worker: {worker}")
                            for task in tasks:
                                task_name = task.get('name', 'Unknown')
                                task_id = task.get('id', 'Unknown')
                                time_start = task.get('time_start', 0)
                                
                                if time_start:
                                    duration = time.time() - time_start
                                    print(f"  🔹 任务: {task_name}")
                                    print(f"     ID: {task_id}")
                                    print(f"     运行时间: {format_duration(duration)}")
                                    
                                    # 对于数据蒸馏任务，尝试获取详细进度
                                    if 'generate_dataset' in task_name or 'pretraining' in task_name:
                                        progress = get_task_progress_from_logs(task_id)
                                        if 'error' not in progress:
                                            print(f"     进度: {progress.get('current_block', 'Unknown')}/{progress.get('total_blocks', 'Unknown')}")
                                            print(f"     成功率: {progress.get('success_rate', 'Unknown')}")
                                            print(f"     预计剩余: {progress.get('estimated_remaining', 'Unknown')}")
                                else:
                                    print(f"  🔹 任务: {task_name} (ID: {task_id}) - 启动时间未知")
                        else:
                            print(f"📍 Worker: {worker} - 无活跃任务")
                else:
                    print("❌ 无法获取活跃任务信息或无活跃任务")
            except Exception as e:
                print(f"❌ 获取Celery任务失败: {str(e)}")
            
            # 检查数据库中的任务
            print("\n💾 数据库任务状态:")
            try:
                # 查询正在运行的任务
                running_tasks = TaskModel.query.filter(
                    TaskModel.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING])
                ).order_by(TaskModel.created_at.desc()).limit(10).all()
                
                if running_tasks:
                    print("\n🔄 正在运行或等待的任务:")
                    for task in running_tasks:
                        duration = ""
                        if task.started_at:
                            duration = format_duration((datetime.utcnow() - task.started_at).total_seconds())
                        
                        print(f"  📝 {task.name}")
                        print(f"     ID: {task.id}")
                        print(f"     状态: {task.status.value}")
                        print(f"     创建时间: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        if task.started_at:
                            print(f"     开始时间: {task.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"     运行时间: {duration}")
                        if task.progress:
                            print(f"     进度: {task.progress}%")
                        print()
                else:
                    print("✅ 没有正在运行的任务")
                
                # 查询最近完成的任务
                completed_tasks = TaskModel.query.filter(
                    TaskModel.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
                ).order_by(TaskModel.completed_at.desc()).limit(5).all()
                
                if completed_tasks:
                    print("\n✅ 最近完成的任务:")
                    for task in completed_tasks:
                        duration = ""
                        if task.started_at and task.completed_at:
                            duration = format_duration((task.completed_at - task.started_at).total_seconds())
                        
                        status_emoji = "✅" if task.status == TaskStatus.COMPLETED else "❌"
                        print(f"  {status_emoji} {task.name}")
                        print(f"     ID: {task.id}")
                        print(f"     状态: {task.status.value}")
                        if task.completed_at:
                            print(f"     完成时间: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        if duration:
                            print(f"     总耗时: {duration}")
                        if task.result and task.status == TaskStatus.FAILED:
                            print(f"     错误: {task.result[:200]}...")
                        print()
                        
            except Exception as e:
                print(f"❌ 查询数据库任务失败: {str(e)}")
            
            # 检查系统资源
            print("\n🖥️  系统资源:")
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                print(f"  CPU使用率: {cpu_percent}%")
                print(f"  内存使用: {memory.percent}% ({memory.used/1024/1024/1024:.1f}GB / {memory.total/1024/1024/1024:.1f}GB)")
                print(f"  磁盘使用: {disk.percent}% ({disk.used/1024/1024/1024:.1f}GB / {disk.total/1024/1024/1024:.1f}GB)")
                
                # 检查Python进程
                python_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        if 'python' in proc.info['name'].lower():
                            python_processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if python_processes:
                    print(f"\n🐍 Python进程 (共{len(python_processes)}个):")
                    # 按CPU使用率排序，显示前5个
                    python_processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                    for proc in python_processes[:5]:
                        print(f"  PID {proc['pid']}: CPU {proc['cpu_percent']:.1f}%, 内存 {proc['memory_percent']:.1f}%")
                        
            except ImportError:
                print("  ⚠️  psutil未安装，无法获取系统资源信息")
            except Exception as e:
                print(f"  ❌ 获取系统资源失败: {str(e)}")
            
            # 检查队列状态
            print("\n📋 队列状态:")
            try:
                stats = celery.control.inspect().stats()
                if stats:
                    for worker, worker_stats in stats.items():
                        broker_stats = worker_stats.get('broker', {})
                        print(f"  📍 Worker: {worker}")
                        print(f"     连接池: {broker_stats.get('connects', 'Unknown')}")
                        print(f"     总任务: {worker_stats.get('total', {}).get('app.tasks', 0)}")
                        print()
            except Exception as e:
                print(f"❌ 获取队列状态失败: {str(e)}")
                
            print("\n" + "=" * 80)
            print("💡 提示:")
            print("  • 如果任务长时间无进度，检查日志文件或考虑重启worker")
            print("  • 数据蒸馏任务可能需要数小时甚至数天，这是正常的")
            print("  • 使用 'python monitor_long_tasks.py' 定期检查任务状态")
            print("  • 如需停止任务，可以使用 celery control 命令")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ 监控脚本执行失败: {str(e)}")
        import traceback
        traceback.print_exc()

def kill_task(task_id: str):
    """终止指定任务"""
    try:
        from app.celery_app import celery
        
        print(f"🛑 正在终止任务: {task_id}")
        
        # 撤销任务
        celery.control.revoke(task_id, terminate=True)
        
        print(f"✅ 任务 {task_id} 已请求终止")
        print("⚠️  注意: 任务可能需要一些时间才会完全停止")
        
    except Exception as e:
        print(f"❌ 终止任务失败: {str(e)}")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        if sys.argv[1] == 'kill' and len(sys.argv) > 2:
            kill_task(sys.argv[2])
        else:
            print("用法:")
            print("  python monitor_long_tasks.py          # 查看任务状态")
            print("  python monitor_long_tasks.py kill <task_id>  # 终止指定任务")
    else:
        monitor_long_tasks()

if __name__ == "__main__":
    main() 