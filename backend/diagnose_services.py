#!/usr/bin/env python
"""
PinData 服务诊断脚本
用于检查 Redis、数据库和 Celery 连接状态
"""

import os
import sys
import subprocess
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_status(service_name, status, message=""):
    """打印服务状态"""
    emoji = "✅" if status else "❌"
    print(f"{emoji} {service_name}: {'正常' if status else '异常'}")
    if message:
        print(f"   {message}")

def check_redis():
    """检查Redis连接"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=16379, db=0)
        r.ping()
        
        # 获取Redis信息
        info = r.info()
        version = info.get('redis_version', 'unknown')
        connected_clients = info.get('connected_clients', 0)
        
        print_status("Redis", True, f"版本: {version}, 连接客户端: {connected_clients}")
        return True
    except Exception as e:
        print_status("Redis", False, f"错误: {str(e)}")
        return False

def check_postgres():
    """检查PostgreSQL连接"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='localhost',
            port=15432,
            database='pindata_dataset',
            user='postgres',
            password='password'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print_status("PostgreSQL", True, f"版本: {version.split(',')[0]}")
        return True
    except Exception as e:
        print_status("PostgreSQL", False, f"错误: {str(e)}")
        return False

def check_minio():
    """检查MinIO连接"""
    try:
        import requests
        response = requests.get('http://localhost:9000/minio/health/live', timeout=5)
        if response.status_code == 200:
            print_status("MinIO", True, "健康检查通过")
            return True
        else:
            print_status("MinIO", False, f"HTTP状态码: {response.status_code}")
            return False
    except Exception as e:
        print_status("MinIO", False, f"错误: {str(e)}")
        return False

def check_celery():
    """检查Celery连接"""
    try:
        from app.celery_app import celery
        
        # 检查worker状态
        stats = celery.control.inspect().stats()
        if stats:
            worker_count = len(stats)
            print_status("Celery Worker", True, f"活跃Worker数: {worker_count}")
            return True
        else:
            print_status("Celery Worker", False, "没有找到活跃的Worker")
            return False
    except Exception as e:
        print_status("Celery Worker", False, f"错误: {str(e)}")
        return False

def check_ports():
    """检查端口占用"""
    ports = {
        15432: "PostgreSQL",
        16379: "Redis",
        9000: "MinIO",
        8897: "API"
    }
    
    print("\n🔍 检查端口状态:")
    for port, service in ports.items():
        try:
            # 使用netstat检查端口
            result = subprocess.run(
                ['netstat', '-an'], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            
            if f":{port}" in result.stdout and "LISTEN" in result.stdout:
                print_status(f"{service} 端口 {port}", True, "正在监听")
            else:
                print_status(f"{service} 端口 {port}", False, "未监听")
                
        except Exception as e:
            print_status(f"{service} 端口 {port}", False, f"检查失败: {str(e)}")

def check_environment():
    """检查环境变量"""
    print("\n🔍 检查环境变量:")
    
    required_env = [
        'DATABASE_URL',
        'REDIS_URL',
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND',
        'MINIO_ENDPOINT',
        'MINIO_ACCESS_KEY',
        'MINIO_SECRET_KEY'
    ]
    
    # 尝试从.env文件加载
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print_status("环境变量文件", True, f"找到: {env_file}")
    else:
        print_status("环境变量文件", False, f"未找到: {env_file}")
    
    missing_vars = []
    for var in required_env:
        if os.getenv(var):
            print_status(f"环境变量 {var}", True, "已设置")
        else:
            print_status(f"环境变量 {var}", False, "未设置")
            missing_vars.append(var)
    
    return len(missing_vars) == 0

def main():
    """主函数"""
    print("=" * 50)
    print("PinData 服务诊断")
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 检查环境变量
    env_ok = check_environment()
    
    print("\n🔍 检查服务连接:")
    
    # 检查各项服务
    redis_ok = check_redis()
    postgres_ok = check_postgres()
    minio_ok = check_minio()
    celery_ok = check_celery()
    
    # 检查端口
    check_ports()
    
    # 总结
    print("\n" + "=" * 50)
    print("诊断总结:")
    print("=" * 50)
    
    services = [
        ("环境变量", env_ok),
        ("Redis", redis_ok),
        ("PostgreSQL", postgres_ok),
        ("MinIO", minio_ok),
        ("Celery", celery_ok)
    ]
    
    all_ok = True
    for service_name, status in services:
        print_status(service_name, status)
        if not status:
            all_ok = False
    
    print("\n💡 建议:")
    if all_ok:
        print("✅ 所有服务运行正常！")
    else:
        print("❌ 发现问题，请按以下步骤排查:")
        print("1. 检查 Docker 服务是否启动: docker-compose up -d")
        print("2. 检查 .env 配置文件是否正确")
        print("3. 查看服务日志: docker-compose logs [服务名]")
        print("4. 重启所有服务: docker-compose restart")
        print("5. 如果问题持续，请检查网络连接和防火墙设置")
    
    print("\n" + "=" * 50)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
