# 任务取消使用指南

## 概述
本指南说明如何使用增强的任务取消功能，特别是对于长时间运行的任务。

## 问题背景
之前的任务取消存在以下问题：
1. 长时间运行的任务（如数据蒸馏）无法及时响应取消信号
2. 任务在重启系统后可能继续运行
3. 某些任务取消后状态不一致

## 解决方案

### 1. 增强的API取消功能
调用 `POST /api/v1/tasks/cancel-all` 现在具有以下增强功能：

#### 新增功能：
- **批量取消**：一次性取消所有正在运行的任务
- **强制终止**：使用 `SIGKILL` 信号强制终止任务
- **孤儿任务清理**：清理未在数据库中记录的活跃任务
- **状态一致性**：确保数据库状态与实际任务状态保持一致

#### 增强的取消步骤：
1. 批量收集所有需要取消的Celery任务ID
2. 使用 `celery.control.revoke()` 批量取消任务
3. 等待1秒让任务响应取消信号
4. 强制终止仍在运行的任务（使用 `SIGKILL`）
5. 更新数据库中的任务状态
6. 清理孤儿任务

### 2. 长时间运行任务的智能取消检测
对于数据蒸馏等长时间运行的任务，现在具有：

#### 取消信号检测：
- **检测频率**：每30秒检查一次取消状态
- **双重检查**：同时检查Celery任务状态和数据库任务状态
- **优雅退出**：检测到取消信号后保存已处理的数据

#### 检测机制：
```python
# 检查Celery任务是否被撤销
if result.state == 'REVOKED':
    logger.info("检测到Celery任务被撤销")
    raise Exception("任务被取消 - Celery任务已撤销")

# 检查数据库中的任务状态
if task_record.status == TaskStatus.CANCELLED:
    logger.info("检测到数据库任务被取消")
    raise Exception("任务被取消 - 数据库状态为已取消")
```

### 3. 强力清理脚本
新增 `force_kill_tasks.py` 脚本，用于彻底清理卡住的任务：

#### 功能：
- **强制终止进程**：杀死所有Celery worker进程
- **清理任务队列**：清空Redis中的任务队列
- **数据库清理**：更新数据库中的任务状态
- **系统检查**：检查清理后的系统状态

#### 使用方法：
```bash
# 检查系统状态
python force_kill_tasks.py --status

# 强制清理（会要求确认）
python force_kill_tasks.py

# 强制清理（跳过确认）
python force_kill_tasks.py --force
```

## 使用步骤

### 1. 正常取消任务
```bash
# 通过API取消所有任务
curl -X POST http://localhost:8897/api/v1/tasks/cancel-all
```

### 2. 如果任务仍在运行
```bash
# 检查系统状态
python force_kill_tasks.py --status

# 强制清理
python force_kill_tasks.py --force
```

### 3. 重启Celery Worker
```bash
# 重启Celery
./start_celery.sh
```

### 4. 验证清理效果
```bash
# 监控任务状态
python monitor_long_tasks.py
```

## 最佳实践

### 1. 定期检查
- 定期使用 `monitor_long_tasks.py` 检查任务状态
- 发现异常任务及时取消

### 2. 分批处理
- 对于大文档，建议分批处理
- 避免单个任务运行时间过长

### 3. 监控资源
- 监控系统资源使用情况
- 确保有足够的内存和CPU

### 4. 备份数据
- 对于重要数据，建议定期备份
- 长时间任务建议启用增量保存

## 故障排查

### 1. 任务取消失败
**症状**: 调用取消API后任务仍在运行
**解决**: 使用强力清理脚本
```bash
python force_kill_tasks.py --force
```

### 2. 系统重启后任务恢复
**症状**: 重启系统后任务继续运行
**解决**: 
1. 清理Redis队列
2. 更新数据库状态
3. 重启Celery worker

### 3. 任务状态不一致
**症状**: 数据库显示已取消但任务仍在运行
**解决**: 
1. 检查系统状态
2. 强制清理
3. 重启服务

## 监控和日志

### 1. 查看任务状态
```bash
# 实时监控
python monitor_long_tasks.py

# 检查特定任务
python monitor_long_tasks.py kill <task_id>
```

### 2. 查看日志
```bash
# Celery日志
tail -f logs/celery_worker.log

# 应用日志
tail -f logs/app.log
```

### 3. 任务心跳检测
长时间运行的任务会输出心跳信息：
```
💓 心跳检测 - 已运行: 2.5小时, 进度: 45.2%, 预计剩余: 3.1小时
📊 当前状态: 成功=450, 失败=5, 正在处理块=455/1000
```

## 注意事项

### 1. 数据丢失风险
- 强制终止任务可能导致部分数据丢失
- 使用前请确保数据已备份

### 2. 系统影响
- 强制清理会影响所有正在运行的任务
- 建议在维护时间窗口内执行

### 3. 配置优化
- 根据系统性能调整并发数
- 合理设置任务超时时间

## 配置说明

### 1. 取消检测频率
```python
# 在任务代码中调整检测频率
cancellation_check_interval = 30  # 30秒检查一次
```

### 2. 心跳检测间隔
```python
# 根据任务长度调整心跳间隔
if len(chunks) > 500:
    heartbeat_interval = 900  # 15分钟
elif len(chunks) > 100:
    heartbeat_interval = 600  # 10分钟
else:
    heartbeat_interval = 300  # 5分钟
```

### 3. 超时设置
```python
# 动态调整超时时间
timeout = _calculate_dynamic_timeout(chunk_text, chunk_index, len(chunks))
```

---

*最后更新: 2024年* 