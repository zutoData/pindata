import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Progress } from '../../../components/ui/progress';
import { Input } from '../../../components/ui/input';
import { Pagination } from '../../../components/ui/pagination';

import {
  ArrowLeftIcon,
  UploadIcon,
  FileTextIcon,
  RefreshCwIcon,
  Trash2Icon,
  DownloadIcon,
  SearchIcon,
  FilterIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  PlayIcon,
  PauseIcon,
  XCircleIcon,
  FolderIcon,
  FileIcon,
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import { 
  FileIcon as LucideFileIcon, 
  FileTextIcon as LucideFileTextIcon,
  CheckCircleIcon as LucideCheckCircleIcon,
  ClockIcon as LucideClockIcon,
  AlertTriangleIcon,
  UploadIcon as LucideUploadIcon,
  MoreHorizontalIcon,
  TrashIcon,
  EyeIcon,
  FileEditIcon,
  CheckSquareIcon,
  SquareIcon,
} from 'lucide-react';

// 导入API相关类型和Hook
import { Library, LibraryFileQueryParams, LibraryFile } from '../../../types/library';
import { FileUpload } from '../FileUpload';
import { useLibraryFiles, useFileActions } from '../../../hooks/useLibraries';
import { useFileConversion } from '../../../hooks/useFileConversion';
import { ConvertToMarkdownDialog, ConversionConfig } from './components/ConvertToMarkdownDialog';
import { ConversionProgress } from './components/ConversionProgress';
import { DataFlowPanel } from '../../../components/DataFlow/DataFlowPanel';
import { LibraryService } from '../../../services/library.service';

interface LibraryDetailsProps {
  onBack: () => void;
  onFileSelect: (file: any) => void;
  library: Library;
}

export const LibraryDetails = ({ onBack, onFileSelect, library }: LibraryDetailsProps): JSX.Element => {
  const { t } = useTranslation();
  const [showUpload, setShowUpload] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error', message: string } | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showConvertDialog, setShowConvertDialog] = useState(false);
  const [conversionJobs, setConversionJobs] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'files' | 'dataflow'>('files');
  const [allConvertableFiles, setAllConvertableFiles] = useState<any[]>([]);
  const [loadingAllFiles, setLoadingAllFiles] = useState(false);
  const [isConvertingAll, setIsConvertingAll] = useState(false);
  const [fetchProgress, setFetchProgress] = useState({ current: 0, total: 0 });
  
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  
  // 构造查询参数 - 使用 useMemo 避免每次渲染都创建新对象
  const queryParams = useMemo<LibraryFileQueryParams>(() => ({
    page: currentPage,
    per_page: pageSize,
    filename: searchTerm || undefined,
    process_status: filterStatus === 'all' ? undefined : filterStatus as any,
  }), [currentPage, pageSize, searchTerm, filterStatus]);
  
  // 使用Hook获取文件列表
  const { files, pagination, loading: filesLoading, error: filesError, fetchFiles, refresh: refreshFiles } = useLibraryFiles(library.id, queryParams);
  const { deleteFile, downloadFile, loading: deleteLoading } = useFileActions();
  const { convertFiles, getConversionJob, cancelConversionJob, loading: convertLoading } = useFileConversion();
  const navigate = useNavigate();

  // 当搜索条件或过滤条件改变时，重置到第一页
  useEffect(() => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  }, [pageSize, searchTerm, filterStatus]);

  // 防抖搜索
  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      // 当搜索或过滤条件改变时，自动触发获取数据
      // 这里不需要手动调用fetchFiles，因为useLibraryFiles会自动响应queryParams的变化
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [searchTerm]);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000); // 3秒后自动隐藏
  };

  const handleUpload = async (files: File[]) => {
    console.log('上传文件:', files);
    setShowUpload(false);
    showNotification('success', t('libraryDetails.uploadSuccess', { count: files.length }));
    
    // 延迟一点时间后刷新文件列表，确保服务器已处理完上传
    setTimeout(() => {
      refreshFiles();
    }, 1000);
  };

  const handleDeleteFile = async (fileId: string, fileName: string) => {
    if (window.confirm(t('libraryDetails.deleteConfirm', { fileName }))) {
      const success = await deleteFile(library.id, fileId);
      if (success) {
        refreshFiles(); // 刷新文件列表
        showNotification('success', t('libraryDetails.deleteSuccess', { fileName }));
      } else {
        showNotification('error', t('libraryDetails.deleteFailed', { fileName }));
      }
    }
  };

  const handleDownloadFile = async (file: any) => {
    try {
      const success = await downloadFile(file.minio_object_name, file.original_filename);
      if (success) {
        showNotification('success', t('libraryDetails.downloadStart', { fileName: file.original_filename }));
      } else {
        showNotification('error', t('libraryDetails.downloadFailed', { fileName: file.original_filename }));
      }
    } catch (error) {
      showNotification('error', t('libraryDetails.downloadFailed', { fileName: file.original_filename }));
    }
  };

  const handleSelectFile = (fileId: string, checked: boolean) => {
    const newSelected = new Set(selectedFiles);
    if (checked) {
      newSelected.add(fileId);
    } else {
      newSelected.delete(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedFiles(new Set(files.map(f => f.id)));
    } else {
      setSelectedFiles(new Set());
    }
  };

  const handleBatchDelete = async () => {
    const selectedFilesList = files.filter(f => selectedFiles.has(f.id));
    const fileNames = selectedFilesList.map(f => f.original_filename).join('、');
    
    if (window.confirm(t('libraryDetails.batchDeleteConfirm', { count: selectedFiles.size, fileNames }))) {
      let successCount = 0;
      let failCount = 0;
      
      for (const file of selectedFilesList) {
        const success = await deleteFile(library.id, file.id);
        if (success) {
          successCount++;
        } else {
          failCount++;
        }
      }
      
      refreshFiles();
      setSelectedFiles(new Set());
      
      if (failCount === 0) {
        showNotification('success', t('libraryDetails.batchDeleteSuccess', { count: successCount }));
      } else {
        showNotification('error', t('libraryDetails.batchDeletePartial', { successCount, failCount }));
      }
    }
  };

  const handleBatchConvertToMD = () => {
    setShowConvertDialog(true);
  };

  // 获取所有可转换的文件
  const fetchAllConvertableFiles = async () => {
    setLoadingAllFiles(true);
    try {
      let allFiles: LibraryFile[] = [];
      let currentPage = 1;
      const perPage = 50; // 减少每页数量，加快响应
      let hasMore = true;
      let maxAttempts = 50; // 减少最大页数，避免过长等待
      
      console.log('开始获取所有可转换文件...');
      
      // 先获取第一页来了解总页数
      const firstResult = await LibraryService.getLibraryFiles(library.id, { 
        page: 1, 
        per_page: perPage
      });
      
      allFiles = [...firstResult.files];
      const totalPages = Math.min(firstResult.pagination.total_pages, maxAttempts);
      setFetchProgress({ current: 1, total: totalPages });
      
      hasMore = firstResult.pagination.has_next;
      currentPage = 2;
      
      // 分页获取剩余文件
      while (hasMore && currentPage <= totalPages) {
        console.log(`正在获取第 ${currentPage}/${totalPages} 页...`);
        
        const result = await LibraryService.getLibraryFiles(library.id, { 
          page: currentPage, 
          per_page: perPage
        });
        
        console.log(`第 ${currentPage} 页获取到 ${result.files.length} 个文件`);
        allFiles = [...allFiles, ...result.files];
        
        // 更新进度
        setFetchProgress({ current: currentPage, total: totalPages });
        
        // 检查是否还有更多页面
        hasMore = result.pagination.has_next;
        currentPage++;
        
        // 给UI一个呼吸的机会，避免卡死
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      
      console.log(`总共获取到 ${allFiles.length} 个文件`);
      
      // 过滤出可转换的文件（排除已经转换过的或正在转换的）
      const convertableFiles = allFiles.filter((file: LibraryFile) => {
        // 只包含已完成处理但还未转换为markdown的文件
        return (file.process_status === 'completed' || file.process_status === 'pending') && 
               !file.converted_format; // 排除已经转换过的文件
      });
      
      console.log(`过滤后有 ${convertableFiles.length} 个可转换文件`);
      
      setAllConvertableFiles(convertableFiles);
      return convertableFiles;
    } catch (error) {
      console.error('获取文件列表失败:', error);
      showNotification('error', '获取文件列表失败');
      return [];
    } finally {
      setLoadingAllFiles(false);
      setFetchProgress({ current: 0, total: 0 });
    }
  };

  // 一键全部转MD功能 - 提供选择弹窗
  const handleConvertAllToMD = async () => {
    // 先获取当前页面可转换的文件数量
    const currentPageConvertable = files.filter((file: LibraryFile) => {
      return (file.process_status === 'completed' || file.process_status === 'pending') && 
             !file.converted_format;
    });
    
    // 如果当前页面有可转换文件，提供选择
    if (currentPageConvertable.length > 0) {
      const choice = window.confirm(
        `检测到当前页面有 ${currentPageConvertable.length} 个可转换文件。\n\n` +
        `点击"确定"：只转换当前页面的文件（快速）\n` +
        `点击"取消"：获取所有分页的文件再转换（可能较慢）`
      );
      
      setIsConvertingAll(true);
      
      if (choice) {
        // 快速模式：只转换当前页面
        setAllConvertableFiles(currentPageConvertable);
        setShowConvertDialog(true);
      } else {
        // 完整模式：获取所有分页
        const convertableFiles = await fetchAllConvertableFiles();
        
        if (convertableFiles.length === 0) {
          showNotification('error', '没有可转换的文件');
          setIsConvertingAll(false);
          return;
        }
        
        setShowConvertDialog(true);
      }
    } else {
      // 当前页面没有可转换文件，直接获取所有文件
      setIsConvertingAll(true);
      const convertableFiles = await fetchAllConvertableFiles();
      
      if (convertableFiles.length === 0) {
        showNotification('error', '没有可转换的文件');
        setIsConvertingAll(false);
        return;
      }
      
      setShowConvertDialog(true);
    }
  };

  const handleConvertConfirm = async (config: ConversionConfig) => {
    let fileIds: string[];
    let count: number;
    
    if (isConvertingAll) {
      // 全部转换模式
      fileIds = allConvertableFiles.map(f => f.id);
      count = allConvertableFiles.length;
    } else {
      // 选中文件转换模式
      const selectedFilesList = files.filter(f => selectedFiles.has(f.id));
      fileIds = selectedFilesList.map(f => f.id);
      count = selectedFiles.size;
    }
    
    const job = await convertFiles(library.id, fileIds, config);
    if (job) {
      showNotification('success', `已提交 ${count} 个文件的转换任务`);
      setSelectedFiles(new Set());
      setShowConvertDialog(false);
      setIsConvertingAll(false);
      setAllConvertableFiles([]);
      setFetchProgress({ current: 0, total: 0 });
      refreshFiles();
      // 添加到转换任务列表
      setConversionJobs(prev => [job, ...prev]);
    } else {
      showNotification('error', '转换任务提交失败');
    }
  };

  const handleRefreshJobs = async () => {
    // 刷新转换任务状态
    for (const job of conversionJobs) {
      const updatedJob = await getConversionJob(job.id);
      if (updatedJob) {
        setConversionJobs(prev => 
          prev.map(j => j.id === job.id ? updatedJob : j)
        );
      }
    }
  };

  const handleCancelJob = async (jobId: string) => {
    const success = await cancelConversionJob(jobId);
    if (success) {
      showNotification('success', t('libraryDetails.jobCancelled'));
      await handleRefreshJobs();
    } else {
      showNotification('error', t('libraryDetails.jobCancelFailed'));
    }
  };

  const handleSingleFileConvert = (fileId: string) => {
    setSelectedFiles(new Set([fileId]));
    setShowConvertDialog(true);
  };

  // 处理分页
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
  };

  // 处理搜索
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  // 处理状态过滤
  const handleFilterChange = (status: string) => {
    setFilterStatus(status);
  };

  const getFileTypeIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return '📄';
      case 'docx':
      case 'doc':
        return '📝';
      case 'pptx':
      case 'ppt':
        return '📊';
      case 'txt':
        return '📃';
      default:
        return '📄';
    }
  };

  const getSelectAllState = () => {
    if (files.length === 0) return { checked: false, indeterminate: false };
    const selectedCount = selectedFiles.size;
    if (selectedCount === 0) return { checked: false, indeterminate: false };
    if (selectedCount === files.length) return { checked: true, indeterminate: false };
    return { checked: false, indeterminate: true };
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <LucideCheckCircleIcon className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <LucideClockIcon className="w-4 h-4 text-blue-500" />;
      case 'failed':
        return <AlertTriangleIcon className="w-4 h-4 text-red-500" />;
      default:
        return <LucideClockIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed':
        return t('rawData.fileStatus.processed');
      case 'processing':
        return t('rawData.fileStatus.processing');
      case 'failed':
        return t('rawData.fileStatus.failed');
      case 'pending':
        return t('rawData.fileStatus.pending');
      default:
        return 'Unknown';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'processing':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'failed':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'pending':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const supportedFormats = [
    // 文档类型
    'pdf', 'docx', 'doc', 'pptx', 'ppt', 'txt', 'md',
    // 图片类型
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg',
    // 视频类型
    'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'
  ];

  const selectAllState = getSelectAllState();
  const selectedFilesForConversion = files.filter(f => selectedFiles.has(f.id));

  const handleFileSelect = (file: any) => {
    // 确保 currentLibrary 和 currentLibrary.id 是有效的
    if (library && library.id) {
      navigate(`/rawdata/library/${library.id}/file/${file.id}`);
    } else {
      console.error("Library ID is missing, cannot navigate to file details.");
      // 可以选择显示一个错误提示给用户
    }
  };

  return (
    <div className="w-full max-w-[1400px] p-6">
      <div className="flex items-center justify-between mb-6">
        <Button
          variant="ghost"
          className="text-[#4f7096] hover:text-[#0c141c] hover:bg-[#e8edf2]"
          onClick={onBack}
        >
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          {t('rawData.backToList')}
        </Button>

        <Button 
          onClick={() => setShowUpload(true)}
          className="bg-[#1977e5] hover:bg-[#1565c0] text-white"
        >
          <LucideUploadIcon className="w-4 h-4 mr-2" />
          {t('rawData.uploadFiles')}
        </Button>
      </div>

      <div className="mb-6">
        <h2 className="text-[26px] font-bold leading-8 text-[#0c141c] mb-2">
          {library.name}
        </h2>
        <p className="text-[#4f7096] mb-4">{library.description}</p>
        <div className="flex gap-2">
          {library.tags.map((tag, index) => (
            <span 
              key={index}
              className="inline-block px-2 py-1 text-xs bg-[#e8edf2] text-[#4f7096] rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* 统计信息 */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        <Card className="border-[#d1dbe8] bg-white p-4">
          <div className="flex items-center">
            <FileIcon className="w-6 h-6 text-[#1977e5] mr-2" />
            <div>
              <p className="text-sm text-[#4f7096]">{t('libraryDetails.totalFiles')}</p>
              <p className="text-lg font-bold text-[#0c141c]">{files.length}</p>
            </div>
          </div>
        </Card>
        
        <Card className="border-[#d1dbe8] bg-white p-4">
          <div className="flex items-center">
            <LucideCheckCircleIcon className="w-6 h-6 text-[#10b981] mr-2" />
            <div>
              <p className="text-sm text-[#4f7096]">{t('libraryDetails.processed')}</p>
              <p className="text-lg font-bold text-[#0c141c]">
                {files.filter(f => f.process_status === 'completed').length}
              </p>
            </div>
          </div>
        </Card>
        
        <Card className="border-[#d1dbe8] bg-white p-4">
          <div className="flex items-center">
            <LucideClockIcon className="w-6 h-6 text-[#f59e0b] mr-2" />
            <div>
              <p className="text-sm text-[#4f7096]">{t('libraryDetails.processing')}</p>
              <p className="text-lg font-bold text-[#0c141c]">
                {files.filter(f => f.process_status === 'processing').length}
              </p>
            </div>
          </div>
        </Card>
        
        <Card className="border-[#d1dbe8] bg-white p-4">
          <div className="flex items-center">
            <AlertTriangleIcon className="w-6 h-6 text-[#ef4444] mr-2" />
            <div>
              <p className="text-sm text-[#4f7096]">{t('libraryDetails.pending')}</p>
              <p className="text-lg font-bold text-[#0c141c]">
                {files.filter(f => f.process_status === 'pending').length}
              </p>
            </div>
          </div>
        </Card>
        
        <Card className="border-[#d1dbe8] bg-white p-4">
          <div className="flex items-center">
            <LucideFileTextIcon className="w-6 h-6 text-[#8b5cf6] mr-2" />
            <div>
              <p className="text-sm text-[#4f7096]">{t('libraryDetails.mdFiles')}</p>
              <p className="text-lg font-bold text-[#0c141c]">
                {files.filter(f => f.converted_format === 'markdown').length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* 转换进度 */}
      {conversionJobs.length > 0 && (
        <ConversionProgress
          jobs={conversionJobs}
          onRefresh={handleRefreshJobs}
          onCancel={handleCancelJob}
          className="mb-6"
        />
      )}

      {/* 标签页导航 */}
      <div className="mb-6">
        <div className="border-b border-[#d1dbe8]">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('files')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'files'
                  ? 'border-[#1977e5] text-[#1977e5]'
                  : 'border-transparent text-[#4f7096] hover:text-[#1977e5] hover:border-[#d1dbe8]'
              }`}
            >
              <FileIcon className="w-4 h-4 inline mr-2" />
              文件管理
            </button>
            <button
              onClick={() => setActiveTab('dataflow')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'dataflow'
                  ? 'border-[#1977e5] text-[#1977e5]'
                  : 'border-transparent text-[#4f7096] hover:text-[#1977e5] hover:border-[#d1dbe8]'
              }`}
            >
              <PlayIcon className="w-4 h-4 inline mr-2" />
              DataFlow 流水线
            </button>
          </nav>
        </div>
      </div>

      {/* 标签页内容 */}
      {activeTab === 'files' && (
        <>
          {/* 文件列表 */}
          <Card className="border-[#d1dbe8] bg-white">
        <div className="p-4 border-b border-[#d1dbe8]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-[#0c141c]">{t('libraryDetails.fileList')}</h3>
              <p className="text-sm text-[#4f7096]">
                {pagination ? `共 ${pagination.total} 个文件` : `共 ${files.length} 个文件`}
                {selectedFiles.size > 0 && (
                  <span className="ml-2 text-[#1977e5]">
                    已选择 {selectedFiles.size} 个
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* 一键全部转MD按钮 */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleConvertAllToMD}
                disabled={convertLoading || loadingAllFiles}
                className="flex items-center gap-2 text-[#1977e5] border-[#1977e5] hover:bg-[#1977e5] hover:text-white"
              >
                {loadingAllFiles ? (
                  <RefreshCwIcon className="w-4 h-4 animate-spin" />
                ) : (
                  <FileTextIcon className="w-4 h-4" />
                )}
                {loadingAllFiles 
                  ? `获取文件中 (${fetchProgress.current}/${fetchProgress.total})`
                  : '一键全部转MD'
                }
              </Button>
              
              {selectedFiles.size > 0 && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleBatchConvertToMD}
                    disabled={convertLoading}
                    className="flex items-center gap-2 text-[#1977e5] border-[#1977e5] hover:bg-[#1977e5] hover:text-white"
                  >
                    <FileEditIcon className="w-4 h-4" />
                    转换选中 ({selectedFiles.size})
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleBatchDelete}
                    disabled={deleteLoading}
                    className="flex items-center gap-2 text-red-600 border-red-300 hover:bg-red-600 hover:text-white"
                  >
                    <Trash2Icon className="w-4 h-4" />
                    删除选中 ({selectedFiles.size})
                  </Button>
                </>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={refreshFiles}
                disabled={filesLoading}
                className="flex items-center gap-2"
              >
                <RefreshCwIcon className={`w-4 h-4 ${filesLoading ? 'animate-spin' : ''}`} />
                刷新
              </Button>
            </div>
          </div>
          
          {/* 搜索和过滤 */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1">
              <div className="relative">
                <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-[#4f7096]" />
                <Input
                  placeholder="搜索文件名..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                  className="pl-9"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <FilterIcon className="w-4 h-4 text-[#4f7096]" />
              <select
                value={filterStatus}
                onChange={(e) => handleFilterChange(e.target.value)}
                className="px-3 py-1 border border-[#d1dbe8] rounded-md text-sm"
              >
                <option value="all">全部状态</option>
                <option value="pending">待处理</option>
                <option value="processing">处理中</option>
                <option value="completed">已完成</option>
                <option value="failed">失败</option>
              </select>
            </div>
          </div>
        </div>

        {filesLoading ? (
          <div className="p-8 text-center text-[#4f7096]">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#1977e5] mx-auto mb-4"></div>
            <p>{t('libraryDetails.loadingFiles')}</p>
          </div>
        ) : filesError ? (
          <div className="p-8 text-center text-red-600">
            <AlertTriangleIcon className="w-12 h-12 mx-auto mb-4" />
            <p>{t('libraryDetails.loadFailed')}: {filesError}</p>
            <Button 
              onClick={refreshFiles} 
              className="mt-4"
              variant="outline"
            >
{t('libraryDetails.retry')}
            </Button>
          </div>
        ) : files.length === 0 ? (
          <div className="p-8 text-center text-[#4f7096]">
            <FileIcon className="w-12 h-12 mx-auto mb-4 text-[#d1dbe8]" />
            <p>{t('libraryDetails.noFiles')}</p>
            <p className="text-xs mt-2">{t('libraryDetails.uploadTip')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      checked={selectAllState.checked}
                      ref={(el) => {
                        if (el) el.indeterminate = selectAllState.indeterminate;
                      }}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="w-4 h-4 text-[#1977e5] bg-gray-100 border-gray-300 rounded focus:ring-[#1977e5] focus:ring-2"
                      aria-label={t('libraryDetails.selectAll')}
                    />
                  </TableHead>
                  <TableHead>{t('libraryDetails.fileName')}</TableHead>
                  <TableHead>{t('libraryDetails.type')}</TableHead>
                  <TableHead>{t('libraryDetails.size')}</TableHead>
                  <TableHead>{t('libraryDetails.status')}</TableHead>
                  <TableHead>{t('libraryDetails.uploadTime')}</TableHead>
                  <TableHead className="text-right">{t('libraryDetails.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((file) => (
                  <TableRow key={file.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(file.id)}
                        onChange={(e) => handleSelectFile(file.id, e.target.checked)}
                        className="w-4 h-4 text-[#1977e5] bg-gray-100 border-gray-300 rounded focus:ring-[#1977e5] focus:ring-2"
                        aria-label={`${t('libraryDetails.selectFile')} ${file.original_filename}`}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{getFileTypeIcon(file.file_type)}</span>
                        <div>
                          <p 
                            className="font-medium text-[#0c141c] cursor-pointer hover:text-[#1977e5] hover:underline"
                            onClick={() => handleFileSelect(file)}
                          >
                            {file.original_filename}
                          </p>
                          <p className="text-xs text-[#4f7096]">
                            {file.file_type.toUpperCase()} • {file.file_size_human}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="uppercase text-xs font-medium text-[#4f7096]">
                        {file.file_type}
                      </span>
                    </TableCell>
                    <TableCell className="text-[#4f7096]">
                      {file.file_size_human}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center">
                        {getStatusIcon(file.process_status)}
                        <span className={`ml-2 px-2 py-1 text-xs rounded-full border ${getStatusColor(file.process_status)}`}>
                          {getStatusText(file.process_status)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-[#4f7096]">
                      {file.uploaded_at ? new Date(file.uploaded_at).toLocaleString('zh-CN') : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSingleFileConvert(file.id)}
                          disabled={convertLoading}
                          className="h-8 w-8 p-0 text-[#4f7096] hover:text-[#1977e5]"
                          title={t('libraryDetails.convertToMDAction')}
                        >
                          <FileEditIcon className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleFileSelect(file)}
                          className="h-8 w-8 p-0 text-[#4f7096] hover:text-[#1977e5]"
                          title={t('libraryDetails.viewDetails')}
                        >
                          <EyeIcon className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteFile(file.id, file.original_filename)}
                          disabled={deleteLoading}
                          className="h-8 w-8 p-0 text-[#4f7096] hover:text-red-600"
                          title={t('libraryDetails.deleteFileAction')}
                        >
                          <TrashIcon className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadFile(file)}
                          disabled={deleteLoading}
                          className="h-8 w-8 p-0 text-[#4f7096] hover:text-blue-600"
                          title={t('libraryDetails.downloadFileAction')}
                        >
                          <DownloadIcon className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        
        {/* 分页组件 */}
        {pagination && pagination.total > 0 && (
          <div className="p-4 border-t border-[#d1dbe8]">
            <Pagination
              currentPage={pagination.page}
              totalPages={pagination.total_pages}
              totalItems={pagination.total}
              pageSize={pagination.per_page}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        )}
      </Card>
        </>
      )}

      {/* DataFlow 流水线标签页 */}
      {activeTab === 'dataflow' && (
        <DataFlowPanel
          libraryId={library.id}
          libraryName={library.name}
          onRefresh={refreshFiles}
        />
      )}

      {/* 文件上传弹窗 */}
      {showUpload && (
        <FileUpload
          onUpload={handleUpload}
          onClose={() => setShowUpload(false)}
          libraryId={library.id}
          supportedFormats={supportedFormats}
        />
      )}

      {/* 转换为MD弹窗 */}
      {showConvertDialog && (
        <ConvertToMarkdownDialog
          open={showConvertDialog}
          onClose={() => {
            setShowConvertDialog(false);
            setIsConvertingAll(false);
            setAllConvertableFiles([]);
            setFetchProgress({ current: 0, total: 0 });
            // 如果是单文件转换，清除选择
            if (selectedFiles.size === 1) {
              setSelectedFiles(new Set());
            }
          }}
          files={isConvertingAll ? allConvertableFiles : selectedFilesForConversion}
          onConfirm={handleConvertConfirm}
          loading={convertLoading || loadingAllFiles}
          title={isConvertingAll ? "一键全部转 Markdown" : "转换为 Markdown"}
          description={
            isConvertingAll 
              ? `将知识库中的所有 ${allConvertableFiles.length} 个可转换文件转换为 Markdown 格式（已排除已转换的文件）` 
              : `将选中的 ${selectedFiles.size} 个文件转换为 Markdown 格式，支持多种转换方式`
          }
        />
      )}

      {/* 通知组件 */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg ${
          notification.type === 'success' 
            ? 'bg-green-50 border-green-200 text-green-800' 
            : 'bg-red-50 border-red-200 text-red-800'
        } border`}>
          <div className="flex items-center">
            {notification.type === 'success' ? (
              <LucideCheckCircleIcon className="w-5 h-5 mr-2" />
            ) : (
              <AlertTriangleIcon className="w-5 h-5 mr-2" />
            )}
            {notification.message}
          </div>
        </div>
      )}
    </div>
  );
}; 