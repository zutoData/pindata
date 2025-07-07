# PinData 用户认证系统

## 功能概述

✅ 完整的用户认证系统已成功集成到 PinData 项目中，包括：

- **用户注册和登录**：完整的前后端认证流程
- **首个用户特权**：第一个注册的用户自动获得超级管理员权限
- **JWT 认证**：基于令牌的安全认证机制
- **权限管理**：角色和权限控制系统
- **会话管理**：多设备登录和会话控制
- **国际化支持**：中英文界面

## 快速开始

### 1. 初始化数据库

```bash
cd backend
python migrations/create_user_management_tables.py
```

### 2. 启动后端服务

```bash
cd backend
python run.py
```

### 3. 启动前端服务

```bash
cd frontend
npm run dev
```

### 4. 首次访问

1. 打开浏览器访问 `http://localhost:5173`
2. 系统会自动跳转到注册页面
3. 注册第一个用户（自动获得管理员权限）
4. 系统会自动登录并跳转到主界面

## 系统特性

### 🔐 认证功能

- **注册/登录**：用户名/邮箱 + 密码
- **记住登录**：持久化登录状态
- **自动令牌刷新**：无感知的令牌更新
- **多设备支持**：跨设备会话管理

### 👑 首个用户特权

- 第一个注册的用户自动获得 `super_admin` 角色
- 拥有所有系统权限
- 自动加入默认组织
- 注册成功后直接登录

### 🛡️ 安全机制

- 密码哈希存储（Werkzeug PBKDF2）
- JWT 令牌认证
- 会话管理和设备跟踪
- 操作审计日志
- 自动登出机制

### 🎯 权限系统

**内置角色：**
- `super_admin`：超级管理员
- `admin`：系统管理员
- `data_admin`：数据管理员
- `user`：普通用户
- `viewer`：只读用户

**权限类型：**
- 系统级权限（通过角色）
- 资源级权限（owner/admin/write/read）
- 组织级权限隔离

## API 端点

### 认证相关
- `POST /api/v1/login` - 用户登录
- `POST /api/v1/register` - 用户注册
- `POST /api/v1/logout` - 用户登出
- `POST /api/v1/refresh` - 刷新令牌
- `GET /api/v1/me` - 获取当前用户信息
- `PUT /api/v1/me` - 更新用户信息
- `POST /api/v1/change-password` - 修改密码

### 用户管理（需要管理员权限）
- `GET /api/v1/users` - 获取用户列表
- `POST /api/v1/users` - 创建用户
- `GET /api/v1/users/{id}` - 获取用户详情
- `PUT /api/v1/users/{id}` - 更新用户
- `DELETE /api/v1/users/{id}` - 删除用户

## 前端组件

### 页面组件
- `Login.tsx` - 登录页面
- `Register.tsx` - 注册页面

### 认证组件
- `ProtectedRoute.tsx` - 路由守卫
- `PermissionGuard.tsx` - 权限守卫
- `AuthProvider.tsx` - 认证上下文

### 状态管理
- `authStore.ts` - 用户认证状态管理
- `auth.service.ts` - 认证相关 API 服务

## 使用示例

### 前端权限检查

```tsx
import { PermissionGuard } from '../components/auth';

// 权限守卫组件
<PermissionGuard permissions={['dataset.create']}>
  <CreateDatasetButton />
</PermissionGuard>

// Hook 方式
const { hasPermission } = useAuthStore();
if (hasPermission('user.manage')) {
  // 显示用户管理功能
}
```

### 受保护的路由

```tsx
<Route path="/admin" element={
  <ProtectedRoute requiredPermissions={['system.manage']}>
    <AdminPanel />
  </ProtectedRoute>
} />
```

### API 请求认证

```typescript
// 自动添加认证头
const response = await authService.getCurrentUser();

// 手动权限检查
if (authStore.hasPermission('dataset.delete')) {
  await deleteDataset(id);
}
```

## 数据库结构

### 核心表
- `users` - 用户基本信息
- `roles` - 角色定义
- `permissions` - 权限定义
- `organizations` - 组织架构

### 关系表
- `user_roles` - 用户角色分配
- `role_permissions` - 角色权限分配
- `user_organizations` - 用户组织关系
- `resource_permissions` - 资源级权限

### 管理表
- `user_sessions` - 用户会话
- `audit_logs` - 操作审计

## 配置说明

### 环境变量
```env
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
DATABASE_URL=postgresql://user:pass@localhost/pindata
```

### 默认配置
- Access Token 过期时间：24小时
- Refresh Token 过期时间：30天
- 自动刷新间隔：5分钟

## 故障排除

### 常见问题

1. **无法注册用户**
   - 检查数据库连接
   - 确认用户管理表已创建
   - 查看后端日志

2. **登录后立即登出**
   - 检查 JWT 密钥配置
   - 确认时间同步
   - 查看浏览器控制台错误

3. **权限检查失败**
   - 确认用户角色分配
   - 检查权限配置
   - 查看审计日志

### 重置系统
```bash
# 重置所有用户数据（谨慎使用）
cd backend
python migrations/create_user_management_tables.py drop
python migrations/create_user_management_tables.py create
```

## 扩展指南

### 添加新权限
1. 在 `migrations/init_user_permissions.sql` 中添加权限
2. 更新相关角色分配
3. 在前端添加权限检查

### 自定义角色
1. 使用管理员账号创建新角色
2. 分配相应权限
3. 为用户分配新角色

### 集成现有模块
```python
# 后端 API 保护
@login_required
@permission_required('dataset.create')
def create_dataset():
    pass
```

```tsx
// 前端组件保护
<PermissionGuard permissions={['dataset.manage']}>
  <DatasetManagement />
</PermissionGuard>
```

## 安全建议

1. **生产环境**：
   - 使用强密码策略
   - 启用 HTTPS
   - 配置安全的 JWT 密钥
   - 设置合理的会话过期时间

2. **权限管理**：
   - 遵循最小权限原则
   - 定期审查用户权限
   - 监控操作审计日志

3. **备份策略**：
   - 定期备份用户数据
   - 保护敏感配置信息

---

🎉 认证系统已成功集成！现在你可以安全地管理用户访问和权限控制了。




