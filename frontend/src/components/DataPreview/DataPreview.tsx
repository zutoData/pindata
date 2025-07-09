/**
 * DataPreview 组件 - 数据集预览组件
 * 
 * 功能特性:
 * - 支持版本切换和预览
 * - 文件列表展示和预览
 * - 文件批量操作 (下载/删除)
 * - 版本信息导出
 * - 文件类型过滤
 * 
 * 使用示例:
 * ```tsx
 * const [currentData, setCurrentData] = useState<DatasetPreviewType>();
 * 
 * const handleVersionChange = async (versionId: string) => {
 *   try {
 *     const newData = await enhancedDatasetService.getDatasetPreview(
 *       datasetId, 
 *       versionId
 *     );
 *     setCurrentData(newData);
 *   } catch (error) {
 *     console.error('切换版本失败:', error);
 *   }
 * };
 * 
 * return (
 *   <DataPreview
 *     data={currentData}
 *     onVersionChange={handleVersionChange}
 *     onRefresh={() => loadData()}
 *     onDataChange={() => loadData()}
 *   />
 * );
 * ```
 */

import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import {
  TableIcon,
  ImageIcon,
  FileTextIcon,
  AlertCircleIcon,
  DownloadIcon,
  EyeIcon,
  UploadIcon,
  Trash2Icon,
  PlusIcon,
  FilterIcon,
  FileIcon,
  FolderIcon,
  MoreHorizontalIcon,
  GitBranch,
  RefreshCw,
  ChevronDownIcon,
  MessageSquareIcon,
  Loader2Icon
} from 'lucide-react';
import { enhancedDatasetService } from '../../services/enhanced-dataset.service';
import { DatasetPreview as DatasetPreviewType, EnhancedDatasetVersion } from '../../types/enhanced-dataset';
import { MediaAnnotationContainer } from '../DataAnnotation/MediaAnnotationContainer';

interface DataPreviewProps {
  data: DatasetPreviewType;
  isLoading: boolean;
  onRefresh?: () => void;
  onDataChange?: () => void;
  onVersionChange?: (versionId: string) => void;
  onPageChange?: (page: number) => void;
  onPerPageChange?: (perPage: number) => void;
}

export type { DataPreviewProps };

export const DataPreview: React.FC<DataPreviewProps> = ({ 
  data, 
  isLoading,
  onRefresh,
  onDataChange,
  onVersionChange,
  onPageChange,
  onPerPageChange
}) => {
  const { t } = useTranslation();
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<string>('all');
  const [isUploading, setIsUploading] = useState(false);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [availableVersions, setAvailableVersions] = useState<EnhancedDatasetVersion[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [isVersionSelectorOpen, setIsVersionSelectorOpen] = useState(false);
  const [isVersionChanging, setIsVersionChanging] = useState(false);
  const [versionChangeError, setVersionChangeError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFileForAnnotation, setSelectedFileForAnnotation] = useState<{
    id: string;
    type: 'image' | 'video';
    url: string;
  } | null>(null);
  const [jumpToPage, setJumpToPage] = useState('');

  // 从 props 获取分页信息
  const { 
    page: currentPage, 
    total_pages: totalPages, 
    total_files: totalFiles,
    per_page: filesPerPage
  } = data.preview;

  // 获取可用版本列表
  useEffect(() => {
    if (data.dataset?.id) {
      loadAvailableVersions();
    }
  }, [data.dataset?.id]);

  // 版本切换时重置相关状态
  useEffect(() => {
    setSelectedFiles(new Set());
    setFilterType('all');
    setVersionChangeError(null);
  }, [data.version?.id]);

  // 点击外部关闭版本选择器
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element;
      if (isVersionSelectorOpen && !target.closest('[data-version-selector]')) {
        setIsVersionSelectorOpen(false);
      }
    };

    if (isVersionSelectorOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isVersionSelectorOpen]);

  // 计算过滤后的文件
  const filteredFiles = data.preview.files.filter(filePreview => {
    if (filterType === 'all') return true;
    return filePreview.file.file_type === filterType;
  });

  // 分页控制函数
  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages && onPageChange) {
      onPageChange(page);
    }
  };

  const handleFilesPerPageChange = (newFilesPerPage: string) => {
    if (onPerPageChange) {
      onPerPageChange(parseInt(newFilesPerPage));
    }
  };
  
  const handleJumpToPage = () => {
    const pageNum = parseInt(jumpToPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      handlePageChange(pageNum);
      setJumpToPage('');
    }
  };

  const handleJumpInputKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleJumpToPage();
    }
  };

  const loadAvailableVersions = async () => {
    if (!data.dataset?.id) return;
    
    try {
      setIsLoadingVersions(true);
      const versions = await enhancedDatasetService.getVersionTree(data.dataset.id);
      setAvailableVersions(versions);
    } catch (error) {
      console.error('获取版本列表失败:', error);
    } finally {
      setIsLoadingVersions(false);
    }
  };

  const handleVersionChange = async (versionId: string) => {
    if (versionId === data.version?.id) {
      setIsVersionSelectorOpen(false);
      return;
    }

    try {
      setIsVersionChanging(true);
      setVersionChangeError(null);
      setIsVersionSelectorOpen(false);
      
      await onVersionChange?.(versionId);
      
    } catch (error) {
      console.error('版本切换失败:', error);
      setVersionChangeError(error instanceof Error ? error.message : '版本切换失败');
    } finally {
      setIsVersionChanging(false);
    }
  };

  const handleDownloadVersion = async (versionId: string) => {
    try {
      await enhancedDatasetService.exportVersionInfo(versionId, 'json');
    } catch (error) {
      console.error('下载版本信息失败:', error);
    }
  };

  const handleDownloadFile = async (objectName: string, filename: string) => {
    try {
      await enhancedDatasetService.downloadDatasetFile(objectName, filename);
    } catch (error) {
      console.error('下载文件失败:', error);
    }
  };

  const handleFileSelect = (fileId: string) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const handleSelectAll = () => {
    const currentPageFileIds = filteredFiles.map(f => f.file.id);
    const allCurrentPageSelected = currentPageFileIds.every(id => selectedFiles.has(id));
    
    const newSelected = new Set(selectedFiles);
    if (allCurrentPageSelected) {
      currentPageFileIds.forEach(id => newSelected.delete(id));
    } else {
      currentPageFileIds.forEach(id => newSelected.add(id));
    }
    setSelectedFiles(newSelected);
  };

  const handleBatchDelete = async () => {
    if (selectedFiles.size === 0 || !data.version) return;
    
    try {
      await enhancedDatasetService.batchFileOperations(
        data.version.id,
        'delete',
        Array.from(selectedFiles)
      );
      setSelectedFiles(new Set());
      onDataChange?.();
    } catch (error) {
      console.error('批量删除失败:', error);
    }
  };

  const handleFileUpload = async (files: File[]) => {
    if (!data.version || files.length === 0) return;
    
    try {
      setIsUploading(true);
      await enhancedDatasetService.addFilesToVersion(data.version.id, files);
      setIsUploadDialogOpen(false);
      onDataChange?.();
    } catch (error) {
      console.error('文件上传失败:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      handleFileUpload(files);
    }
  };

  const fileTypes = [...new Set(data.preview.file_types ? Object.keys(data.preview.file_types) : [])];

  const renderPreviewContent = (filePreview: any) => {
    const { file, preview } = filePreview;

    // 添加更详细的错误处理
    if (!preview) {
      console.error('Preview data is missing for file:', file);
      return (
        <div className="flex items-center justify-center py-8 text-red-500">
          <AlertCircleIcon className="w-5 h-5 mr-2" />
          <span>{t('dataPreview.previewDataMissing')}</span>
        </div>
      );
    }

    if (preview.type === 'error') {
      return (
        <div className="flex items-center justify-center py-8 text-red-500">
          <AlertCircleIcon className="w-5 h-5 mr-2" />
          <span>{preview.message}</span>
        </div>
      );
    }

    try {
      switch (preview.type) {
        case 'tabular':
          return renderTabularPreview(preview);
        case 'json':
          return renderJsonPreview(preview);
        case 'text':
          return renderTextPreview(preview);
        case 'image':
          return renderImagePreview(preview);
        case 'unsupported':
          return (
            <div className="flex items-center justify-center py-8 text-gray-500">
              <FileTextIcon className="w-5 h-5 mr-2" />
              <span>{preview.message || t('dataPreview.previewDeveloping')}</span>
            </div>
          );
        default:
          console.warn('Unknown preview type:', preview.type);
          return (
            <div className="flex items-center justify-center py-8 text-gray-500">
              <span>{t('dataPreview.unsupportedPreview')}</span>
            </div>
          );
      }
    } catch (error) {
      console.error('Error rendering preview content:', error, 'Preview data:', preview);
      return (
        <div className="flex items-center justify-center py-8 text-red-500">
          <AlertCircleIcon className="w-5 h-5 mr-2" />
          <span>{t('dataPreview.previewRenderError')}</span>
        </div>
      );
    }
  };

  const renderTabularPreview = (preview: any) => {
    if (!preview.items || preview.items.length === 0) {
      return <div className="text-center py-4 text-gray-500">{t('dataPreview.noDataToPreview')}</div>;
    }

    const columns = preview.stats?.columns || [];
    
    return (
      <div className="space-y-4">
        {/* 统计信息 */}
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">
            {t('dataPreview.totalRows')}: {preview.stats?.total_rows || preview.total_items}
          </Badge>
          <Badge variant="secondary">
            {t('dataPreview.columns')}: {preview.stats?.total_columns || columns.length}
          </Badge>
          <Badge variant="secondary">
            {t('dataPreview.preview')}: {preview.preview_count} {t('dataPreview.rows')}
          </Badge>
        </div>

        {/* 表格预览 */}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse border border-gray-200">
            <thead>
              <tr className="bg-gray-50">
                <th className="border border-gray-200 px-2 py-1 text-xs font-medium text-left">
                  #
                </th>
                {columns.map((col: string) => (
                  <th key={col} className="border border-gray-200 px-2 py-1 text-xs font-medium text-left">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.items.map((item: any) => (
                <tr key={item.index} className="hover:bg-gray-50">
                  <td className="border border-gray-200 px-2 py-1 text-xs text-gray-600">
                    {item.index}
                  </td>
                  {columns.map((col: string) => (
                    <td key={col} className="border border-gray-200 px-2 py-1 text-xs">
                      {String(item.data?.[col] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderJsonPreview = (preview: any) => {
    if (!preview.items || preview.items.length === 0) {
      return <div className="text-center py-4 text-gray-500">{t('dataPreview.noDataToPreview')}</div>;
    }

    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Badge variant="secondary">
            {t('dataPreview.format')}: {preview.format}
          </Badge>
          <Badge variant="secondary">
            {t('dataPreview.totalItems')}: {preview.total_items}
          </Badge>
          <Badge variant="secondary">
            {t('dataPreview.preview')}: {preview.preview_count} {t('dataPreview.items')}
          </Badge>
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {preview.items.map((item: any) => (
            <div key={item.index} className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-500 mb-2">{t('dataPreview.entry')} #{item.index}</div>
              <pre className="text-xs overflow-x-auto">
                {JSON.stringify(item.data, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderTextPreview = (preview: any) => {
    if (!preview.items || preview.items.length === 0) {
      return <div className="text-center py-4 text-gray-500">{t('dataPreview.noDataToPreview')}</div>;
    }

    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Badge variant="secondary">
            {t('dataPreview.totalRows')}: {preview.total_items}
          </Badge>
          <Badge variant="secondary">
            {t('dataPreview.preview')}: {preview.preview_count} {t('dataPreview.rows')}
          </Badge>
        </div>

        <div className="bg-gray-50 rounded p-4 max-h-96 overflow-y-auto">
          {preview.items.map((item: any) => (
            <div key={item.index} className="flex text-sm">
              <span className="text-gray-400 mr-3 w-8 text-right">
                {item.index}
              </span>
              <span className="flex-1 font-mono">
                {item.content}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderImagePreview = (preview: any) => {
    if (preview.format === 'single_image' && preview.items && preview.items.length > 0) {
      const item = preview.items[0];
      return (
        <div className="space-y-4">
          <div className="flex gap-2">
            <Badge variant="secondary">
              {t('dataPreview.size')}: {item.metadata?.width} × {item.metadata?.height}
            </Badge>
            <Badge variant="secondary">
              {t('dataPreview.mode')}: {item.metadata?.mode}
            </Badge>
            <Badge variant="secondary">
              {t('common.size')}: {(item.metadata?.size / 1024).toFixed(1)} KB
            </Badge>
          </div>

          <div className="flex justify-center">
            <img
              src={item.thumbnail}
              alt={item.filename}
              className="max-w-full max-h-64 rounded border"
            />
          </div>
        </div>
      );
    }

    return (
      <div className="text-center py-8 text-gray-500">
        <ImageIcon className="w-8 h-8 mx-auto mb-2" />
        <span>{preview.message || t('dataPreview.imagePreviewDeveloping')}</span>
      </div>
    );
  };

  const getFileTypeIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case 'text':
        return <FileTextIcon className="w-4 h-4" />;
      case 'image':
        return <ImageIcon className="w-4 h-4" />;
      default:
        return <FileTextIcon className="w-4 h-4" />;
    }
  };

  const renderFileActions = (filePreview: any) => {
    const { file } = filePreview;
    const isMediaFile = file.file_type.toLowerCase() === 'image' || file.file_type.toLowerCase() === 'video';

    return (
      <div className="flex gap-2">
        {isMediaFile && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedFileForAnnotation({
              id: file.id,
              type: file.file_type.toLowerCase() as 'image' | 'video',
              url: file.url
            })}
          >
            <MessageSquareIcon className="w-4 h-4 mr-2" />
            {t('dataPreview.annotate')}
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => window.open(file.url, '_blank')}
        >
          <EyeIcon className="w-4 h-4 mr-2" />
          {t('dataPreview.preview')}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleDownloadFile(file.minio_object_name, file.filename)}
        >
          <DownloadIcon className="w-4 h-4 mr-2" />
          {t('dataPreview.download')}
        </Button>
      </div>
    );
  };

  if (!data.preview || totalFiles === 0) {
    return (
      <Card className="p-6">
        <div className="text-center py-8 text-gray-500">
          <FileTextIcon className="w-8 h-8 mx-auto mb-2" />
          <p>{data.preview?.message || t('dataPreview.noPreviewData')}</p>
          {onRefresh && (
            <Button 
              variant="outline" 
              className="mt-4"
              onClick={onRefresh}
            >
              {t('dataPreview.refreshPreview')}
            </Button>
          )}
          {data.version && !data.version.is_deprecated && (
            <Button 
              className="mt-2 ml-2"
              onClick={handleUploadClick}
            >
              <PlusIcon className="w-4 h-4 mr-2" />
              {t('dataPreview.addFiles')}
            </Button>
          )}
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* 总览信息和操作栏 */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">{t('dataPreview.title')}</h3>
            <div className="space-y-1">
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>{t('dataPreview.totalFiles')}: {data.preview.total_files}</span>
              </div>
              <p className="text-sm text-gray-600">
                {t('dataPreview.dataset')}: {data.dataset?.name}
              </p>
              
              {/* 版本选择器 */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">{t('dataPreview.version')}:</span>
                <div className="relative" data-version-selector>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setIsVersionSelectorOpen(!isVersionSelectorOpen)}
                    disabled={isLoadingVersions || isVersionChanging}
                  >
                    {isVersionChanging ? (
                      <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                    ) : (
                      <GitBranch className="w-3 h-3 mr-1" />
                    )}
                    {isVersionChanging ? t('dataPreview.switching') : (data.version?.version || t('dataPreview.noVersion'))}
                    {!isVersionChanging && data.version?.is_default && (
                      <Badge variant="secondary" className="ml-1 h-4 px-1 text-xs">
                        {t('dataPreview.default')}
                      </Badge>
                    )}
                    {!isVersionChanging && <ChevronDownIcon className="w-3 h-3 ml-1" />}
                  </Button>
                  
                  {isVersionSelectorOpen && (
                    <div className="absolute top-8 left-0 z-50 w-80 bg-white border rounded-md shadow-lg">
                      <div className="p-2 border-b">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{t('dataPreview.selectVersion')}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={loadAvailableVersions}
                            disabled={isLoadingVersions}
                          >
                            <RefreshCw className={`w-3 h-3 ${isLoadingVersions ? 'animate-spin' : ''}`} />
                          </Button>
                        </div>
                      </div>
                      <div className="max-h-64 overflow-y-auto">
                        {availableVersions.length === 0 ? (
                          <div className="p-3 text-sm text-gray-500 text-center">
                            {isLoadingVersions ? t('dataPreview.loading') : t('dataPreview.noVersion')}
                          </div>
                        ) : (
                          availableVersions.map((version) => (
                            <div
                              key={version.id}
                              className={`group relative border-l-2 ${
                                version.id === data.version?.id 
                                  ? 'border-blue-500 bg-blue-50' 
                                  : 'border-transparent hover:bg-gray-50'
                              } ${isVersionChanging ? 'opacity-50' : ''}`}
                            >
                              <div
                                className={`p-2 ${
                                  version.id === data.version?.id || isVersionChanging 
                                    ? 'cursor-default' 
                                    : 'cursor-pointer'
                                }`}
                                onClick={() => {
                                  if (version.id !== data.version?.id && !isVersionChanging) {
                                    handleVersionChange(version.id);
                                  }
                                }}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-medium">
                                        {version.version}
                                      </span>
                                      {version.id === data.version?.id && (
                                        <Badge variant="default" className="h-4 px-1 text-xs">
                                          {t('dataPreview.current')}
                                        </Badge>
                                      )}
                                      {version.is_default && (
                                        <Badge variant="secondary" className="h-4 px-1 text-xs">
                                          {t('dataPreview.default')}
                                        </Badge>
                                      )}
                                      {version.is_draft && (
                                        <Badge variant="outline" className="h-4 px-1 text-xs">
                                          {t('dataPreview.draft')}
                                        </Badge>
                                      )}
                                      {version.is_deprecated && (
                                        <Badge variant="destructive" className="h-4 px-1 text-xs">
                                          {t('dataPreview.deprecated')}
                                        </Badge>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1 line-clamp-1">
                                      {version.commit_message}
                                    </div>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                                      <span>{version.author}</span>
                                      <span>{version.file_count} {t('dataPreview.files')}</span>
                                      <span>{version.total_size_formatted}</span>
                                      <span>{new Date(version.created_at).toLocaleDateString()}</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                              
                              {/* 版本操作按钮 */}
                              <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDownloadVersion(version.id);
                                  }}
                                  title={t('dataPreview.downloadFile')}
                                >
                                  <DownloadIcon className="w-3 h-3" />
                                </Button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              <p className="text-sm text-gray-600">
                {t('dataPreview.totalFiles')}: {data.preview.total_files}
              </p>
              
              {/* 版本切换错误提示 */}
              {versionChangeError && (
                <div className="flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 mt-2">
                  <AlertCircleIcon className="w-4 h-4" />
                  <span>{t('dataPreview.versionSwitchFailed')}: {versionChangeError}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto h-6 w-6 p-0"
                    onClick={() => setVersionChangeError(null)}
                  >
                    ×
                  </Button>
                </div>
              )}
              {data.version && (
                <div className="flex gap-2 mt-2">
                  <Badge variant={data.version.is_default ? "default" : "secondary"}>
                    {data.version.is_default ? t('dataPreview.defaultVersion') : data.version.version_type}
                  </Badge>
                  <Badge variant="outline">
                    {data.version.author}
                  </Badge>
                  <Badge variant="outline">
                    {data.version.total_size_formatted}
                  </Badge>
                  {data.version.is_draft && (
                    <Badge variant="outline">{t('dataPreview.draft')}</Badge>
                  )}
                  {data.version.is_deprecated && (
                    <Badge variant="destructive">{t('dataPreview.deprecated')}</Badge>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
            {onRefresh && (
              <Button variant="outline" size="sm" onClick={onRefresh}>
                <EyeIcon className="w-4 h-4 mr-2" />
                {t('dataPreview.refreshPreview')}
              </Button>
            )}
            {data.version && (
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => enhancedDatasetService.exportVersionInfo(data.version!.id)}
              >
                {t('dataPreview.exportInfo')}
              </Button>
            )}
          </div>
        </div>

        {/* 文件操作栏 */}
        <div className="flex items-center justify-between border-t pt-4">
          <div className="flex items-center gap-4">
            {/* 文件类型过滤 */}
            <div className="flex items-center gap-2">
              <FilterIcon className="w-4 h-4" />
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('dataPreview.allTypes')}</SelectItem>
                  {fileTypes.map(type => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 全选/取消全选 */}
            <div className="flex items-center gap-2">
              <Checkbox
                checked={(() => {
                  const currentPageFileIds = filteredFiles.map(f => f.file.id);
                  return currentPageFileIds.length > 0 && currentPageFileIds.every(id => selectedFiles.has(id));
                })()}
                onCheckedChange={handleSelectAll}
              />
              <span className="text-sm">
                {t('dataPreview.selected')} {selectedFiles.size} / {filteredFiles.length} {t('dataPreview.files')}
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            {/* 批量删除 */}
            {selectedFiles.size > 0 && data.version && !data.version.is_deprecated && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleBatchDelete}
              >
                <Trash2Icon className="w-4 h-4 mr-2" />
                {t('dataPreview.deleteSelected')} ({selectedFiles.size})
              </Button>
            )}

            {/* 添加文件 */}
            {data.version && !data.version.is_deprecated && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={handleFileInputChange}
                />
                <Button
                  size="sm"
                  onClick={handleUploadClick}
                  disabled={isUploading}
                >
                  <PlusIcon className="w-4 h-4 mr-2" />
                  {isUploading ? t('dataPreview.uploading') : t('dataPreview.addFiles')}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* 文件预览列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2Icon className="w-6 h-6 animate-spin mr-2" />
          <span>{t('dataPreview.loading')}...</span>
        </div>
      ) : (
        filteredFiles.map((filePreview, index) => {
          const isUnsupported = filePreview.preview?.type === 'unsupported' || 
                                filePreview.preview?.type === 'error';
          
          return (
            <Card key={filePreview.file.id} className={`${isUnsupported ? 'p-4' : 'p-6'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Checkbox
                    checked={selectedFiles.has(filePreview.file.id)}
                    onCheckedChange={() => handleFileSelect(filePreview.file.id)}
                  />
                  {getFileTypeIcon(filePreview.file.file_type)}
                  <div>
                    <h4 className="font-medium">{filePreview.file.filename}</h4>
                    <p className="text-sm text-gray-600">
                      {filePreview.file.file_type} · {filePreview.file.file_size_formatted}
                    </p>
                    {filePreview.file.checksum && (
                      <p className="text-xs text-gray-400 font-mono">
                        {t('dataPreview.checksum')}: {filePreview.file.checksum.slice(0, 8)}...
                      </p>
                    )}
                    {isUnsupported && (
                      <p className="text-xs text-gray-500 mt-1">
                        {filePreview.preview?.message || t('dataPreview.unsupportedFileType')}
                      </p>
                    )}
                  </div>
                </div>
                {renderFileActions(filePreview)}
              </div>

              {/* 只有支持的文件类型才显示预览内容 */}
              {!isUnsupported && (
                <div className="mt-4">
                  {renderPreviewContent(filePreview)}
                </div>
              )}
            </Card>
          );
        })
      )}

      {/* 分页导航 */}
      {totalFiles > 0 && (
        <Card className="mt-6 p-4">
          <div className="flex flex-col lg:flex-row justify-between items-center gap-4">
            {/* 文件信息显示 */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">
                {t('dataPreview.showing')} {((currentPage - 1) * filesPerPage) + 1}-{Math.min(currentPage * filesPerPage, totalFiles)} / {totalFiles} {t('dataPreview.files')}
              </span>
            </div>
            
            {/* 分页控制区域 */}
            <div className="flex flex-col sm:flex-row items-center gap-4">
              {/* 基础分页控制 */}
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="min-w-16"
                >
                  {t('dataPreview.previous')}
                </Button>
                
                <span className="text-sm text-gray-600 px-3 min-w-20 text-center">
                  {t('dataPreview.page')} {currentPage} / {totalPages}
                </span>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="min-w-16"
                >
                  {t('dataPreview.next')}
                </Button>
              </div>
              
              {/* 跳转到指定页 - 总是显示 */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">{t('dataPreview.jumpTo')}:</span>
                <Input
                  type="number"
                  value={jumpToPage}
                  onChange={(e) => setJumpToPage(e.target.value)}
                  onKeyPress={handleJumpInputKeyPress}
                  placeholder="页码"
                  className="w-16 h-8 text-sm text-center"
                  min="1"
                  max={totalPages}
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleJumpToPage}
                  disabled={!jumpToPage || parseInt(jumpToPage) < 1 || parseInt(jumpToPage) > totalPages}
                  className="min-w-12"
                >
                  {t('dataPreview.go')}
                </Button>
              </div>
            </div>
            
            {/* 每页文件数设置 */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">{t('dataPreview.filesPerPage')}:</span>
              <Select value={filesPerPage.toString()} onValueChange={handleFilesPerPageChange}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5</SelectItem>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </Card>
      )}



      {/* 版本信息卡片 */}
      {data.version && (
        <Card className="p-6">
          <h4 className="font-semibold mb-3">{t('dataPreview.versionInfo')}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">{t('dataPreview.commitHash')}:</span>
              <span className="ml-2 font-mono">{data.version.commit_hash}</span>
            </div>
            <div>
              <span className="text-gray-600">{t('dataPreview.createTime')}:</span>
              <span className="ml-2">{new Date(data.version.created_at).toLocaleString()}</span>
            </div>
            <div className="md:col-span-2">
              <span className="text-gray-600">{t('dataPreview.commitMessage')}:</span>
              <span className="ml-2">{data.version.commit_message}</span>
            </div>
          </div>
        </Card>
      )}

      {/* 标注对话框 */}
      <Dialog open={!!selectedFileForAnnotation} onOpenChange={() => setSelectedFileForAnnotation(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              {selectedFileForAnnotation?.type === 'image' 
                ? t('annotation.imageAnnotation')
                : t('annotation.videoAnnotation')}
            </DialogTitle>
          </DialogHeader>
          {selectedFileForAnnotation && (
            <MediaAnnotationContainer
              fileId={selectedFileForAnnotation.id}
              fileType={selectedFileForAnnotation.type}
              fileUrl={selectedFileForAnnotation.url}
              onClose={() => setSelectedFileForAnnotation(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}; 