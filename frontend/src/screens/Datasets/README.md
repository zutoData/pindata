# 数据集管理系统

这是一个全面升级的数据集管理系统，提供类似 Hugging Face 的完整功能，支持多种数据集创建和管理方式。

## 📋 功能特性

### 🎯 核心功能
- **数据集浏览** - 美观的卡片式布局展示数据集
- **数据预览** - 实时预览数据集内容和结构
- **README显示** - 支持Markdown格式的详细文档
- **版本控制** - Git风格的版本管理系统
- **多格式支持** - JSONL、CSV、Parquet等多种格式

### 🚀 创建方式
1. **文件提取** - 从原始文件中通过大模型提取结构化数据
2. **网络下载** - 支持HuggingFace、GitHub、Kaggle等平台
3. **模型蒸馏** - 直接从大模型生成高质量数据集

### 💼 管理功能
- **任务监控** - 实时跟踪数据集创建进度
- **状态管理** - 支持暂停、恢复、停止等操作
- **错误处理** - 详细的错误信息和重试机制
- **批量操作** - 支持批量下载、删除等操作

## 📁 文件结构

```
frontend/src/screens/Datasets/
├── README.md           # 本文档
├── index.tsx          # 导出文件
├── Datasets.tsx       # 数据集列表页面
├── DatasetDetail.tsx  # 数据集详情页面
├── CreateDataset.tsx  # 创建数据集页面
└── DatasetTasks.tsx   # 任务监控页面
```

## 🎨 页面组件

### 1. Datasets.tsx - 数据集列表
**功能亮点：**
- 响应式卡片布局
- 高级搜索和筛选
- 任务类型分类显示
- 标签和元数据展示
- 收藏和下载功能

**主要状态：**
```typescript
const [searchQuery, setSearchQuery] = useState('');
const [sortBy, setSortBy] = useState('trending');
const [filterBy, setFilterBy] = useState('all');
const [taskFilter, setTaskFilter] = useState('all');
```

### 2. DatasetDetail.tsx - 数据集详情
**功能亮点：**
- 多标签页展示不同内容
- 数据样本实时预览
- 文件结构浏览
- README渲染显示
- 版本历史管理
- 完整的使用示例

**标签页内容：**
- `preview` - 数据预览
- `files` - 文件浏览
- `readme` - 文档显示
- `versions` - 版本历史
- `usage` - 使用示例

### 3. CreateDataset.tsx - 创建数据集
**功能亮点：**
- 三种创建方式切换
- 智能文件选择器
- 提取指令编辑
- 预检查功能
- 表单验证

**创建方式：**
- `extract` - 文件提取（支持PDF、TXT、CSV等）
- `download` - 网络下载（HuggingFace、GitHub等）
- `distill` - 模型蒸馏（GPT-4、Claude等）

### 4. DatasetTasks.tsx - 任务监控
**功能亮点：**
- 实时进度监控
- 状态图标展示
- 任务操作控制
- 统计信息面板
- 错误信息展示

**任务状态：**
- `pending` - 等待中
- `running` - 进行中
- `completed` - 已完成
- `failed` - 失败
- `paused` - 已暂停

## 🎯 使用指南

### 创建新数据集

1. **从文件提取**
   ```
   选择源文件 → 设置提取模型 → 编写提取指令 → 开始创建
   ```

2. **从网络下载**
   ```
   输入URL → 预检查验证 → 确认格式 → 开始下载
   ```

3. **模型蒸馏生成**
   ```
   选择源模型 → 编写蒸馏提示 → 设置样本数量 → 开始生成
   ```

### 数据集管理

1. **浏览和搜索**
   - 使用搜索框快速查找
   - 按任务类型筛选
   - 按热门度、时间等排序

2. **查看详情**
   - 预览数据样本
   - 查看文件结构
   - 阅读README文档
   - 检查版本历史

3. **下载使用**
   - 直接下载数据文件
   - 查看使用示例代码
   - 复制API调用方法

## 🔧 技术特性

### UI/UX 设计
- **现代化界面** - 遵循最新设计规范
- **响应式布局** - 支持各种屏幕尺寸
- **一致的视觉语言** - 统一的颜色和图标
- **流畅的交互** - 平滑的动画和过渡

### 组件架构
- **TypeScript支持** - 完整的类型定义
- **React Hooks** - 现代化的状态管理
- **shadcn/ui组件** - 高质量的UI组件库
- **Lucide图标** - 精美的矢量图标

### 数据流设计
```typescript
interface Dataset {
  id: string;
  name: string;
  owner: string;
  description: string;
  lastUpdated: string;
  size: string;
  downloads: number;
  likes: number;
  versions: number;
  license: string;
  taskType: string;
  tags: string[];
  language?: string;
  featured?: boolean;
}
```

## 🎨 样式规范

### 颜色主题
- **主色调：** `#1977e5` (蓝色)
- **文本色：** `#0c141c` (深灰)
- **辅助色：** `#4f7096` (中灰)
- **边框色：** `#d1dbe8` (浅灰)
- **背景色：** `#f0f4f8` (极浅灰)

### 图标使用
- **数据库：** `DatabaseIcon` - 数据集标识
- **文件：** `FileIcon` - 文件类型
- **下载：** `DownloadIcon` - 下载操作
- **心形：** `HeartIcon` - 收藏功能
- **眼睛：** `EyeIcon` - 预览查看

## 🚀 扩展功能

### 计划中的功能
1. **高级分析** - 数据质量评估和统计分析
2. **协作功能** - 多用户协作和权限管理
3. **API集成** - 完整的RESTful API
4. **数据可视化** - 图表和图形展示
5. **自动化流水线** - 数据处理自动化

### 集成能力
- **大模型API** - GPT、Claude、Gemini等
- **数据平台** - HuggingFace、Kaggle、GitHub
- **云存储** - AWS S3、Google Cloud等
- **版本控制** - Git LFS、DVC等

## 📝 开发说明

### 依赖要求
```json
{
  "react": "^18.0.0",
  "react-i18next": "^12.0.0",
  "lucide-react": "^0.263.0",
  "class-variance-authority": "^0.7.0"
}
```

### 组件导入
```typescript
import { 
  Datasets, 
  DatasetDetail, 
  CreateDataset, 
  DatasetTasks 
} from './screens/Datasets';
```

### 路由配置示例
```typescript
const routes = [
  { path: '/datasets', component: Datasets },
  { path: '/datasets/:id', component: DatasetDetail },
  { path: '/datasets/create', component: CreateDataset },
  { path: '/datasets/tasks', component: DatasetTasks }
];
```

这个升级后的数据集系统提供了完整的数据集生命周期管理，从创建到使用的全流程支持，具备了现代化数据科学平台的所有核心功能。 