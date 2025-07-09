import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { DataPreview } from '../../components/DataPreview/DataPreview';
import { VersionManager } from '../../components/DatasetVersions/VersionManager';
import { enhancedDatasetService } from '../../services/enhanced-dataset.service';
import { datasetService } from '../../services/dataset.service';
import { 
  DatasetPreview, 
  EnhancedDatasetVersion 
} from '../../types/enhanced-dataset';
import { Dataset } from '../../types/dataset';
import {
  ArrowLeftIcon,
  DatabaseIcon,
  DownloadIcon,
  HeartIcon,
  GitBranchIcon,
  TagIcon,
  CalendarIcon,
  HardDriveIcon,
  Loader2Icon,
  AlertCircleIcon,
  UserIcon,
  FileText,
  Calendar,
  User,
  Download,
  Eye,
  Settings,
  Info,
  PackageIcon,
  CheckCircleIcon
} from 'lucide-react';

export const DatasetDetailScreen = (): JSX.Element => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [previewData, setPreviewData] = useState<DatasetPreview | null>(null);
  const [currentVersion, setCurrentVersion] = useState<EnhancedDatasetVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('preview');
  const [error, setError] = useState<string | null>(null);
  
  // 打包下载相关状态
  const [isPackageDownloading, setIsPackageDownloading] = useState(false);
  const [packageInfo, setPackageInfo] = useState<{
    total_files: number;
    total_size: number;
    total_size_formatted: string;
    enhanced_versions: number;
    traditional_versions: number;
    raw_data_sources: number;
    estimated_time: string;
  } | null>(null);
  const [packageInfoLoading, setPackageInfoLoading] = useState(false);

  // 获取数据集详情
  const fetchDatasetDetail = async () => {
    if (!id) return;
    
    try {
      setLoading(true);
      setError(null);
      const [datasetInfo, preview] = await Promise.all([
        datasetService.getDatasetById(id),
        enhancedDatasetService.getDatasetPreview(parseInt(id))
      ]);
      setDataset(datasetInfo);
      setPreviewData(preview);
      setCurrentVersion(preview.version);
      
      // 获取打包信息
      fetchPackageInfo();
    } catch (err) {
      console.error('获取数据集详情失败:', err);
      setError(err instanceof Error ? err.message : t('datasets.error'));
    } finally {
      setLoading(false);
    }
  };

  // 获取打包信息
  const fetchPackageInfo = async () => {
    if (!id) return;
    
    try {
      setPackageInfoLoading(true);
      const info = await datasetService.getPackageInfo(id);
      setPackageInfo(info);
    } catch (err) {
      console.error('获取打包信息失败:', err);
      // 打包信息获取失败不影响主要功能
    } finally {
      setPackageInfoLoading(false);
    }
  };

  // 处理版本切换
  const handleVersionChange = async (versionId: string) => {
    if (!id) return;
    
    try {
      const newPreviewData = await enhancedDatasetService.getDatasetPreview(
        parseInt(id),
        versionId
      );
      setPreviewData(newPreviewData);
      setCurrentVersion(newPreviewData.version);
    } catch (err) {
      console.error('版本切换失败:', err);
      setError(err instanceof Error ? err.message : t('datasets.error'));
    }
  };

  // 处理数据变更（文件上传、删除等）
  const handleDataChange = () => {
    // 重新获取当前版本的数据
    if (currentVersion) {
      handleVersionChange(currentVersion.id);
    } else {
      fetchDatasetDetail();
    }
  };

  // 处理点赞
  const handleLike = async () => {
    if (!dataset) return;
    
    try {
      const response = await datasetService.likeDataset(dataset.id);
      setDataset(prev => prev ? { ...prev, likes: response.likes } : null);
    } catch (err) {
      console.error('点赞失败:', err);
    }
  };

  // 处理打包下载
  const handlePackageDownload = async () => {
    if (!dataset) return;
    
    try {
      setIsPackageDownloading(true);
      
      // 获取打包的blob数据
      const blob = await datasetService.packageDownloadDataset(dataset.id);
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${dataset.owner}_${dataset.name}_${dataset.id}.zip`;
      document.body.appendChild(a);
      a.click();
      
      // 清理
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      // 更新下载次数（如果需要）
      try {
        const response = await datasetService.downloadDataset(dataset.id);
        setDataset(prev => prev ? { ...prev, downloads: response.downloads } : null);
      } catch (updateErr) {
        console.warn('更新下载次数失败:', updateErr);
      }
      
    } catch (err) {
      console.error('打包下载失败:', err);
      setError(err instanceof Error ? err.message : '下载失败');
    } finally {
      setIsPackageDownloading(false);
    }
  };

  // 处理下载 (保留原有的单独下载逻辑)
  const handleDownload = async () => {
    if (!dataset) return;
    
    try {
      const response = await datasetService.downloadDataset(dataset.id);
      setDataset(prev => prev ? { ...prev, downloads: response.downloads } : null);
      
      if (response.download_url) {
        window.open(response.download_url, '_blank');
      }
    } catch (err) {
      console.error('下载失败:', err);
    }
  };

  // 格式化数字
  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
  };

  // 获取任务类型颜色
  const getTaskTypeColor = (taskType: string): string => {
    const colors: { [key: string]: string } = {
      'Natural Language Processing': 'bg-blue-100 text-blue-800',
      'Question Answering': 'bg-green-100 text-green-800',
      'Text Classification': 'bg-purple-100 text-purple-800',
      'Computer Vision': 'bg-orange-100 text-orange-800',
      'Code Generation': 'bg-indigo-100 text-indigo-800',
      'Audio': 'bg-pink-100 text-pink-800'
    };
    return colors[taskType] || 'bg-gray-100 text-gray-800';
  };

  useEffect(() => {
    fetchDatasetDetail();
  }, [id]);

  if (loading) {
    return (
      <div className="w-full max-w-[1200px] p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2Icon className="w-8 h-8 animate-spin text-[#1977e5]" />
          <span className="ml-2 text-[#4f7096]">{t('datasets.loading')}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-[1200px] p-6">
        <div className="flex items-center justify-center py-12">
          <AlertCircleIcon className="w-6 h-6 text-red-500 mr-2" />
          <span className="text-red-600">{error}</span>
          <Button 
            variant="outline" 
            className="ml-4"
            onClick={fetchDatasetDetail}
          >
            {t('datasets.retry')}
          </Button>
        </div>
      </div>
    );
  }

  if (!dataset || !previewData) {
    return (
      <div className="w-full max-w-[1200px] p-6">
        <div className="flex items-center justify-center py-12">
          <span className="text-[#4f7096]">{t('datasets.noDatasets')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link to="/datasets">
            <Button variant="outline" size="sm">
              <ArrowLeftIcon className="w-4 h-4 mr-2" />
              {t('datasets.detail.backToList')}
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <DatabaseIcon className="w-6 h-6 text-[#1977e5]" />
            <h1 className="text-[28px] font-bold leading-8 text-[#0c141c]">
              {dataset.owner}/{dataset.name}
            </h1>
            {dataset.featured && (
              <Badge className="bg-[#ff6b35] text-white">{t('datasets.recommended')}</Badge>
            )}
          </div>
        </div>
        
        {/* 打包下载按钮 */}
        <div className="flex items-center gap-2">
          <Button
            onClick={handlePackageDownload}
            disabled={isPackageDownloading}
            className="bg-[#1977e5] hover:bg-[#1565c0] text-white"
            size="lg"
          >
            {isPackageDownloading ? (
              <>
                <Loader2Icon className="w-4 h-4 mr-2 animate-spin" />
                {t('datasets.detail.packaging')}
              </>
            ) : (
              <>
                <PackageIcon className="w-4 h-4 mr-2" />
                {t('datasets.detail.packageDownload')}
              </>
            )}
          </Button>
          
          {packageInfo && (
            <div className="text-sm text-gray-600">
              <div className="text-right">
                <div className="font-medium">{packageInfo.total_files} {t('datasets.detail.files')}</div>
                <div>{packageInfo.total_size_formatted}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="preview" className="flex items-center gap-2">
            <Eye className="w-4 h-4" />
            {t('datasets.detail.dataPreview')}
          </TabsTrigger>
          <TabsTrigger value="versions" className="flex items-center gap-2">
            <GitBranchIcon className="w-4 h-4" />
            {t('datasets.detail.versionManagement')}
          </TabsTrigger>
          <TabsTrigger value="info" className="flex items-center gap-2">
            <Info className="w-4 h-4" />
            {t('datasets.detail.detailInfo')}
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings className="w-4 h-4" />
            {t('datasets.detail.settings')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="space-y-4">
          <DataPreview 
            data={previewData} 
            onRefresh={() => fetchDatasetDetail()}
            onVersionChange={handleVersionChange}
            onDataChange={handleDataChange}
          />
        </TabsContent>

        <TabsContent value="versions" className="space-y-4">
          <VersionManager
            datasetId={parseInt(id!)}
            currentVersion={currentVersion || undefined}
            onVersionChange={(newVersion) => {
              setCurrentVersion(newVersion);
              // 同步更新预览数据
              handleVersionChange(newVersion.id);
            }}
          />
        </TabsContent>

        <TabsContent value="info" className="space-y-4">
          {/* 打包下载信息卡片 */}
          {packageInfo && (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">{t('datasets.detail.packageInfo')}</h3>
                <Button
                  onClick={handlePackageDownload}
                  disabled={isPackageDownloading}
                  className="bg-[#1977e5] hover:bg-[#1565c0] text-white"
                >
                  {isPackageDownloading ? (
                    <>
                      <Loader2Icon className="w-4 h-4 mr-2 animate-spin" />
                      {t('datasets.detail.packaging')}
                    </>
                  ) : (
                    <>
                      <PackageIcon className="w-4 h-4 mr-2" />
                      {t('datasets.detail.packageDownload')}
                    </>
                  )}
                </Button>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{packageInfo.total_files}</div>
                  <div className="text-sm text-gray-600">{t('datasets.detail.totalFiles')}</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{packageInfo.total_size_formatted}</div>
                  <div className="text-sm text-gray-600">{t('datasets.detail.totalSize')}</div>
                </div>
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{packageInfo.estimated_time}</div>
                  <div className="text-sm text-gray-600">{t('datasets.detail.estimatedTime')}</div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center gap-2">
                  <CheckCircleIcon className="w-5 h-5 text-green-500" />
                  <span className="text-sm">
                    {packageInfo.enhanced_versions} {t('datasets.detail.enhancedVersions')}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircleIcon className="w-5 h-5 text-green-500" />
                  <span className="text-sm">
                    {packageInfo.traditional_versions} {t('datasets.detail.traditionalVersions')}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircleIcon className="w-5 h-5 text-green-500" />
                  <span className="text-sm">
                    {packageInfo.raw_data_sources} {t('datasets.detail.rawDataSources')}
                  </span>
                </div>
              </div>
              
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <h4 className="font-medium mb-2">{t('datasets.detail.packageIncludes')}</h4>
                <ul className="text-sm text-gray-600 space-y-1">
                  <li>• {t('datasets.detail.allVersionFiles')}</li>
                  <li>• {t('datasets.detail.datasetMetadata')}</li>
                  <li>• {t('datasets.detail.readmeDocumentation')}</li>
                  <li>• {t('datasets.detail.versionHistory')}</li>
                </ul>
              </div>
            </Card>
          )}
          
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">{t('datasets.detail.detailInfo')}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.datasetId')}</label>
                  <p className="mt-1">{dataset.id}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.name')}</label>
                  <p className="mt-1">{dataset.name}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.status')}</label>
                  <p className="mt-1">
                    <Badge variant="default">
                      {t('datasets.detail.published')}
                    </Badge>
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.createdAt')}</label>
                  <p className="mt-1">{dataset.created_at ? new Date(dataset.created_at).toLocaleString('zh-CN') : dataset.created}</p>
                </div>
              </div>
              
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.currentVersion')}</label>
                  <p className="mt-1">{currentVersion?.version || t('datasets.detail.noVersion')}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.versionType')}</label>
                  <p className="mt-1">
                    {currentVersion && (
                      <Badge variant="outline">
                        {currentVersion.version_type}
                      </Badge>
                    )}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.fileCount')}</label>
                  <p className="mt-1">{currentVersion?.file_count || 0} {t('datasets.detail.files')}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">{t('datasets.detail.totalSize')}</label>
                  <p className="mt-1">{currentVersion?.total_size_formatted || '0B'}</p>
                </div>
              </div>
            </div>

            {dataset.description && (
              <div className="mt-6">
                <label className="text-sm font-medium text-gray-600">{t('datasets.detail.description')}</label>
                <p className="mt-2 text-gray-700">{dataset.description}</p>
              </div>
            )}

            {currentVersion && (
              <div className="mt-6">
                <label className="text-sm font-medium text-gray-600">{t('datasets.detail.versionInfo')}</label>
                <div className="mt-2 p-4 bg-gray-50 rounded-lg">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-medium">{t('datasets.detail.commitHash')}:</span>
                      <span className="ml-2 font-mono">{currentVersion.commit_hash}</span>
                    </div>
                    <div>
                      <span className="font-medium">{t('datasets.detail.author')}:</span>
                      <span className="ml-2">{currentVersion.author}</span>
                    </div>
                    <div className="md:col-span-2">
                      <span className="font-medium">{t('datasets.detail.commitMessage')}:</span>
                      <span className="ml-2">{currentVersion.commit_message}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="space-y-4">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">{t('datasets.detail.settings')}</h3>
            <div className="text-gray-500">
              {t('datasets.detail.settingsInDevelopment')}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}; 