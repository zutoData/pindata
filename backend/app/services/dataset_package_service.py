import os
import tempfile
import zipfile
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import current_app

from app.models.dataset import Dataset, DatasetVersion, DatasetDownload
from app.models.dataset_version import EnhancedDatasetVersion, EnhancedDatasetFile
from app.models.raw_data import RawData
from app.services.storage_service import storage_service
from app.db import db

logger = logging.getLogger(__name__)


class DatasetPackageService:
    """数据集打包服务"""
    
    def __init__(self):
        self.temp_dir = None
        self.zip_path = None
        
    def create_dataset_package(self, dataset_id: int, user_ip: str = None, user_agent: str = None) -> str:
        """
        创建数据集打包文件
        
        Args:
            dataset_id: 数据集ID
            user_ip: 用户IP地址
            user_agent: 用户代理
            
        Returns:
            str: 打包文件路径
        """
        try:
            dataset = Dataset.query.get_or_404(dataset_id)
            
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp()
            safe_dataset_name = self._safe_filename(f"{dataset.owner}_{dataset.name}")
            self.zip_path = os.path.join(self.temp_dir, f"{safe_dataset_name}_{dataset_id}.zip")
            
            # 创建ZIP文件
            with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                files_count = 0
                
                # 收集所有类型的文件
                enhanced_files = self._collect_enhanced_files(dataset_id, zipf)
                traditional_files = self._collect_traditional_files(dataset_id, zipf)
                raw_files = self._collect_raw_files(dataset_id, zipf)
                
                files_count = enhanced_files + traditional_files + raw_files
                
                # 添加元数据和文档
                self._add_metadata(dataset, files_count, zipf)
                self._add_readme(dataset, files_count, zipf)
                
                logger.info(f"数据集 {dataset_id} 打包完成，包含 {files_count} 个文件")
            
            # 记录下载
            self._record_download(dataset_id, user_ip, user_agent)
            
            return self.zip_path
            
        except Exception as e:
            logger.error(f"创建数据集包失败: {str(e)}")
            raise
    
    def _collect_enhanced_files(self, dataset_id: int, zipf: zipfile.ZipFile) -> int:
        """收集增强数据集版本文件"""
        files_count = 0
        
        try:
            enhanced_versions = EnhancedDatasetVersion.query.filter_by(dataset_id=dataset_id).all()
            for version in enhanced_versions:
                version_files = EnhancedDatasetFile.query.filter_by(version_id=version.id).all()
                for file in version_files:
                    try:
                        # 从MinIO下载文件
                        file_content = storage_service.get_file(
                            object_name=file.minio_object_name,
                            bucket_name=file.minio_bucket
                        )
                        
                        # 添加到ZIP文件
                        zip_path_in_archive = f"enhanced_versions/{version.version}/{file.filename}"
                        zipf.writestr(zip_path_in_archive, file_content)
                        files_count += 1
                        logger.info(f"已添加增强版本文件: {file.filename}")
                        
                    except Exception as e:
                        logger.warning(f"无法下载增强版本文件 {file.filename}: {str(e)}")
                        
        except Exception as e:
            logger.warning(f"收集增强版本文件失败: {str(e)}")
            
        return files_count
    
    def _collect_traditional_files(self, dataset_id: int, zipf: zipfile.ZipFile) -> int:
        """收集传统数据集版本文件"""
        files_count = 0
        
        try:
            traditional_versions = DatasetVersion.query.filter_by(dataset_id=dataset_id).all()
            for version in traditional_versions:
                if version.file_path:
                    try:
                        # 尝试从不同的bucket获取文件
                        file_content = storage_service.get_file(
                            object_name=version.file_path
                        )
                        
                        # 添加到ZIP文件
                        zip_path_in_archive = f"versions/{version.version}/{os.path.basename(version.file_path)}"
                        zipf.writestr(zip_path_in_archive, file_content)
                        files_count += 1
                        logger.info(f"已添加传统版本文件: {version.file_path}")
                        
                    except Exception as e:
                        logger.warning(f"无法下载传统版本文件 {version.file_path}: {str(e)}")
                        
        except Exception as e:
            logger.warning(f"收集传统版本文件失败: {str(e)}")
            
        return files_count
    
    def _collect_raw_files(self, dataset_id: int, zipf: zipfile.ZipFile) -> int:
        """收集原始数据文件"""
        files_count = 0
        
        try:
            raw_data_files = RawData.query.filter_by(dataset_id=dataset_id).all()
            for raw_file in raw_data_files:
                try:
                    # 从MinIO下载文件
                    file_content = storage_service.get_file(
                        object_name=raw_file.minio_object_name,
                        bucket_name='raw-data'  # 原始数据通常在raw-data bucket
                    )
                    
                    # 添加到ZIP文件
                    zip_path_in_archive = f"raw_data/{raw_file.filename}"
                    zipf.writestr(zip_path_in_archive, file_content)
                    files_count += 1
                    logger.info(f"已添加原始数据文件: {raw_file.filename}")
                    
                except Exception as e:
                    logger.warning(f"无法下载原始数据文件 {raw_file.filename}: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"收集原始数据文件失败: {str(e)}")
            
        return files_count
    
    def _add_metadata(self, dataset: Dataset, files_count: int, zipf: zipfile.ZipFile):
        """添加数据集元数据文件"""
        try:
            metadata = {
                'dataset_info': {
                    'id': dataset.id,
                    'name': dataset.name,
                    'owner': dataset.owner,
                    'description': dataset.description,
                    'task_type': dataset.task_type,
                    'language': dataset.language,
                    'license': dataset.license,
                    'downloads': dataset.downloads,
                    'likes': dataset.likes,
                    'featured': dataset.featured,
                    'created_at': dataset.created_at.isoformat() if dataset.created_at else None,
                    'updated_at': dataset.updated_at.isoformat() if dataset.updated_at else None
                },
                'package_info': {
                    'files_count': files_count,
                    'package_date': datetime.utcnow().isoformat(),
                    'package_version': '1.0',
                    'packager': 'PinData Dataset Package Service'
                },
                'file_structure': {
                    'enhanced_versions/': '增强版本文件目录',
                    'versions/': '传统版本文件目录',
                    'raw_data/': '原始数据文件目录',
                    'metadata.json': '数据集元数据文件',
                    'README.md': '说明文档'
                }
            }
            
            metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
            zipf.writestr('metadata.json', metadata_json)
            
        except Exception as e:
            logger.warning(f"添加元数据文件失败: {str(e)}")
    
    def _add_readme(self, dataset: Dataset, files_count: int, zipf: zipfile.ZipFile):
        """添加README文件"""
        try:
            readme_content = f"""# {dataset.name}

## 数据集信息
- **拥有者**: {dataset.owner}
- **描述**: {dataset.description or '无描述'}
- **任务类型**: {dataset.task_type or '未指定'}
- **语言**: {dataset.language or '未指定'}
- **许可证**: {dataset.license or '未指定'}
- **下载次数**: {dataset.downloads}
- **点赞数**: {dataset.likes}

## 文件结构
```
{self._safe_filename(f"{dataset.owner}_{dataset.name}")}/
├── enhanced_versions/          # 增强版本文件
│   └── [version]/
├── versions/                   # 传统版本文件
│   └── [version]/
├── raw_data/                   # 原始数据文件
├── metadata.json               # 数据集元数据
└── README.md                   # 此文件
```

## 打包信息
- **打包时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
- **包含文件数**: {files_count}
- **打包版本**: 1.0

## 使用说明
此数据集包含了所有相关的数据文件和元数据。请根据具体的任务类型和许可证要求使用这些数据。

### 文件说明
- `enhanced_versions/`: 包含增强版本的数据集文件，支持版本控制
- `versions/`: 包含传统版本的数据集文件
- `raw_data/`: 包含原始数据文件
- `metadata.json`: 包含数据集的详细元数据信息

### 许可证信息
请遵守数据集的许可证要求：{dataset.license or '未指定'}

### 引用信息
如果您使用了此数据集，请适当引用：
```
数据集名称: {dataset.name}
拥有者: {dataset.owner}
获取时间: {datetime.utcnow().strftime('%Y-%m-%d')}
```

---
由 PinData 平台生成
"""
            zipf.writestr('README.md', readme_content)
            
        except Exception as e:
            logger.warning(f"添加README文件失败: {str(e)}")
    
    def _record_download(self, dataset_id: int, user_ip: str = None, user_agent: str = None):
        """记录下载"""
        try:
            dataset = Dataset.query.get(dataset_id)
            if not dataset:
                return
                
            # 创建下载记录
            download = DatasetDownload(
                dataset_id=dataset_id,
                user_id=user_ip or 'unknown',
                ip_address=user_ip or 'unknown',
                user_agent=user_agent or 'unknown'
            )
            db.session.add(download)
            
            # 更新下载数
            dataset.downloads += 1
            db.session.commit()
            
        except Exception as e:
            logger.warning(f"记录下载失败: {str(e)}")
    
    def _safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        import re
        # 移除或替换不安全的字符
        safe_name = re.sub(r'[^\w\-_.]', '_', filename)
        # 限制长度
        return safe_name[:100]
    
    def cleanup(self):
        """清理临时文件"""
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"已清理临时目录: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {str(e)}")
    
    def get_dataset_package_info(self, dataset_id: int) -> Dict[str, Any]:
        """获取数据集打包信息"""
        try:
            dataset = Dataset.query.get_or_404(dataset_id)
            
            # 统计文件数量
            enhanced_count = 0
            traditional_count = 0
            raw_count = 0
            
            # 统计增强版本文件
            enhanced_versions = EnhancedDatasetVersion.query.filter_by(dataset_id=dataset_id).all()
            for version in enhanced_versions:
                enhanced_count += EnhancedDatasetFile.query.filter_by(version_id=version.id).count()
            
            # 统计传统版本文件
            traditional_versions = DatasetVersion.query.filter_by(dataset_id=dataset_id).all()
            traditional_count = len([v for v in traditional_versions if v.file_path])
            
            # 统计原始数据文件
            raw_count = RawData.query.filter_by(dataset_id=dataset_id).count()
            
            total_files = enhanced_count + traditional_count + raw_count
            
            return {
                'dataset_id': dataset_id,
                'dataset_name': dataset.name,
                'owner': dataset.owner,
                'file_counts': {
                    'enhanced_versions': enhanced_count,
                    'traditional_versions': traditional_count,
                    'raw_data': raw_count,
                    'total': total_files
                },
                'estimated_size': '计算中...',  # 可以后续优化计算实际大小
                'package_available': total_files > 0
            }
            
        except Exception as e:
            logger.error(f"获取数据集打包信息失败: {str(e)}")
            raise


# 创建全局服务实例
dataset_package_service = DatasetPackageService() 