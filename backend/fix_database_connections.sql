-- 清理数据库连接和事务状态的SQL脚本
-- 该脚本用于修复 "Can't reconnect until invalid transaction is rolled back" 错误

-- 1. 查看当前活跃的连接和事务状态
SELECT 
    pid,
    state,
    query_start,
    state_change,
    application_name,
    backend_start,
    query
FROM pg_stat_activity 
WHERE state != 'idle' 
AND pid != pg_backend_pid()
ORDER BY state_change DESC;

-- 2. 查看锁定的事务
SELECT 
    t.schemaname,
    t.tablename,
    l.locktype,
    l.page,
    l.virtualtransaction,
    l.pid,
    l.mode,
    l.granted
FROM pg_locks l
JOIN pg_stat_user_tables t ON l.relation = t.relid
WHERE NOT l.granted
ORDER BY t.schemaname, t.tablename;

-- 3. 终止长时间运行的空闲事务（超过5分钟）
-- 注意：这会终止可能阻塞其他操作的长时间空闲事务
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity 
WHERE state = 'idle in transaction'
AND state_change < NOW() - INTERVAL '5 minutes'
AND pid != pg_backend_pid();

-- 4. 终止长时间运行的活跃查询（超过30分钟）
-- 注意：这会终止可能导致问题的长时间运行查询
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity 
WHERE state = 'active'
AND query_start < NOW() - INTERVAL '30 minutes'
AND pid != pg_backend_pid()
AND query NOT LIKE '%pg_stat_activity%';

-- 5. 清理可能的死锁
-- 注意：这会强制终止可能导致死锁的进程
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity 
WHERE state IN ('idle in transaction (aborted)', 'disabled')
AND pid != pg_backend_pid();

-- 6. 检查是否还有问题连接
SELECT 
    COUNT(*) as problematic_connections,
    string_agg(DISTINCT state, ', ') as states
FROM pg_stat_activity 
WHERE state IN ('idle in transaction', 'idle in transaction (aborted)', 'disabled')
AND pid != pg_backend_pid();

-- 使用说明：
-- 1. 如果出现 "Can't reconnect until invalid transaction is rolled back" 错误
-- 2. 首先运行查询部分（SELECT 语句）来查看问题
-- 3. 然后根据需要运行清理部分（pg_terminate_backend 语句）
-- 4. 建议在非生产时间执行，因为会终止现有连接 