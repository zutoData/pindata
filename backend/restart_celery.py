#!/usr/bin/env python3
"""
重启Celery Worker的脚本
用于修复数据库连接问题和清理僵死任务
"""

import os
import sys
import signal
import time
import subprocess
import logging
from typing import List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_celery_processes() -> List[dict]:
    """查找所有Celery进程"""
    try:
        # 使用 pgrep 查找 celery 进程
        result = subprocess.run(['pgrep', '-f', 'celery'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            
            processes = []
            for pid in pids:
                try:
                    # 获取进程详细信息
                    proc_info = subprocess.run(['ps', '-p', str(pid), '-o', 'pid,ppid,cmd'], 
                                              capture_output=True, text=True)
                    if proc_info.returncode == 0:
                        lines = proc_info.stdout.strip().split('\n')
                        if len(lines) > 1:  # 跳过标题行
                            parts = lines[1].split(None, 2)
                            if len(parts) >= 3:
                                processes.append({
                                    'pid': int(parts[0]),
                                    'ppid': int(parts[1]),
                                    'cmd': parts[2]
                                })
                except (ValueError, subprocess.SubprocessError):
                    continue
            
            return processes
        return []
    except subprocess.SubprocessError as e:
        logger.error(f"查找Celery进程失败: {e}")
        return []

def stop_celery_processes(processes: List[dict], timeout: int = 30) -> bool:
    """停止Celery进程"""
    if not processes:
        logger.info("没有找到Celery进程")
        return True
    
    logger.info(f"找到 {len(processes)} 个Celery进程")
    for proc in processes:
        logger.info(f"PID: {proc['pid']}, 命令: {proc['cmd'][:100]}...")
    
    # 首先尝试优雅停止
    logger.info("尝试优雅停止Celery进程...")
    for proc in processes:
        try:
            os.kill(proc['pid'], signal.SIGTERM)
            logger.info(f"发送SIGTERM信号给进程 {proc['pid']}")
        except OSError as e:
            logger.warning(f"无法发送SIGTERM给进程 {proc['pid']}: {e}")
    
    # 等待进程停止
    start_time = time.time()
    while time.time() - start_time < timeout:
        remaining_processes = find_celery_processes()
        if not remaining_processes:
            logger.info("所有Celery进程已停止")
            return True
        
        logger.info(f"等待进程停止... 剩余 {len(remaining_processes)} 个进程")
        time.sleep(2)
    
    # 如果优雅停止失败，强制杀死
    remaining_processes = find_celery_processes()
    if remaining_processes:
        logger.warning("优雅停止失败，强制杀死进程...")
        for proc in remaining_processes:
            try:
                os.kill(proc['pid'], signal.SIGKILL)
                logger.info(f"强制杀死进程 {proc['pid']}")
            except OSError as e:
                logger.error(f"无法强制杀死进程 {proc['pid']}: {e}")
        
        # 再次检查
        time.sleep(2)
        final_processes = find_celery_processes()
        if final_processes:
            logger.error(f"仍有 {len(final_processes)} 个进程无法停止")
            return False
    
    logger.info("所有Celery进程已停止")
    return True

def start_celery_worker() -> bool:
    """启动Celery worker"""
    logger.info("启动Celery worker...")
    
    # 获取项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    
    # 设置环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root
    
    try:
        # 启动Celery worker
        cmd = [
            sys.executable, '-m', 'celery', 
            '--app=app.celery_app:celery',
            'worker',
            '--loglevel=info',
            '--concurrency=4',
            '--prefetch-multiplier=1',
            '--max-tasks-per-child=1000',
            '--queues=long_running,conversion,default'
        ]
        
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        # 在后台启动
        process = subprocess.Popen(
            cmd,
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待一段时间确保启动成功
        time.sleep(5)
        
        if process.poll() is None:
            logger.info(f"Celery worker启动成功，PID: {process.pid}")
            return True
        else:
            stdout, stderr = process.communicate()
            logger.error(f"Celery worker启动失败")
            logger.error(f"STDOUT: {stdout.decode()}")
            logger.error(f"STDERR: {stderr.decode()}")
            return False
            
    except subprocess.SubprocessError as e:
        logger.error(f"启动Celery worker失败: {e}")
        return False

def check_database_connections():
    """检查数据库连接状态"""
    logger.info("检查数据库连接状态...")
    
    try:
        # 这里可以添加数据库连接检查逻辑
        # 例如连接数据库并执行简单查询
        from app import create_app
        from app.db import db
        
        app = create_app()
        with app.app_context():
            try:
                # 执行简单查询测试连接
                db.session.execute('SELECT 1')
                db.session.commit()
                logger.info("数据库连接正常")
                return True
            except Exception as e:
                logger.error(f"数据库连接异常: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
                return False
                
    except Exception as e:
        logger.error(f"无法检查数据库连接: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始重启Celery worker...")
    
    # 1. 检查数据库连接
    if not check_database_connections():
        logger.warning("数据库连接有问题，但继续重启Celery")
    
    # 2. 查找并停止现有的Celery进程
    processes = find_celery_processes()
    if not stop_celery_processes(processes):
        logger.error("停止Celery进程失败")
        return False
    
    # 3. 等待一段时间确保资源清理
    logger.info("等待资源清理...")
    time.sleep(3)
    
    # 4. 启动新的Celery worker
    if not start_celery_worker():
        logger.error("启动Celery worker失败")
        return False
    
    logger.info("Celery worker重启完成")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 