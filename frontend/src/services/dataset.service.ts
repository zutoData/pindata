import { apiClient } from '../lib/api-client';
import { config } from '../lib/config';
import {
  Dataset,
  DatasetDetail,
  DatasetVersion,
  CreateDatasetRequest,
  UpdateDatasetRequest,
  CreateDatasetVersionRequest,
  DatasetQueryParams,
  DatasetStats,
  DatasetListResponse,
  LikeResponse,
  DownloadResponse,
  DatasetImportStatus,
} from '../types/dataset';

export class DatasetService {
  /**
   * 获取数据集列表
   */
  static async getDatasets(params?: DatasetQueryParams): Promise<DatasetListResponse> {
    const response = await apiClient.get<DatasetListResponse>('/api/v1/datasets', params);
    return response;
  }

  /**
   * 获取单个数据集详情
   */
  static async getDatasetById(id: string | number): Promise<DatasetDetail> {
    const response = await apiClient.get<DatasetDetail>(`/api/v1/datasets/${id}`);
    return response;
  }

  /**
   * 创建数据集
   */
  static async createDataset(data: CreateDatasetRequest): Promise<Dataset> {
    const response = await apiClient.post<Dataset>('/api/v1/datasets', data);
    return response;
  }

  /**
   * 更新数据集
   */
  static async updateDataset(id: string | number, data: UpdateDatasetRequest): Promise<Dataset> {
    const response = await apiClient.put<Dataset>(`/api/v1/datasets/${id}`, data);
    return response;
  }

  /**
   * 删除数据集
   */
  static async deleteDataset(id: string | number): Promise<void> {
    await apiClient.delete(`/api/v1/datasets/${id}`);
  }

  /**
   * 点赞数据集
   */
  static async likeDataset(id: string | number): Promise<LikeResponse> {
    const response = await apiClient.post<LikeResponse>(`/api/v1/datasets/${id}/like`);
    return response;
  }

  /**
   * 下载数据集
   */
  static async downloadDataset(id: string | number): Promise<DownloadResponse> {
    const response = await apiClient.post<DownloadResponse>(`/api/v1/datasets/${id}/download`);
    return response;
  }

  /**
   * 打包下载数据集
   */
  static async packageDownloadDataset(id: string | number): Promise<Blob> {
    // 使用配置中的API地址
    const url = `${config.apiBaseUrl}/datasets/${id}/package-download`;
    
    // 获取token，如果不存在则抛出错误
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw new Error('用户未登录');
    }
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        // Token可能过期了，提示用户重新登录
        throw new Error('登录已过期，请重新登录');
      }
      throw new Error(`下载失败: ${response.status}`);
    }
    
    return response.blob();
  }

  /**
   * 获取数据集打包信息
   */
  static async getPackageInfo(id: string | number): Promise<{
    total_files: number;
    total_size: number;
    total_size_formatted: string;
    enhanced_versions: number;
    traditional_versions: number;
    raw_data_sources: number;
    estimated_time: string;
  }> {
    const response = await apiClient.get<{
      total_files: number;
      total_size: number;
      total_size_formatted: string;
      enhanced_versions: number;
      traditional_versions: number;
      raw_data_sources: number;
      estimated_time: string;
    }>(`/api/v1/datasets/${id}/package-info`);
    return response;
  }

  /**
   * 获取数据集版本列表
   * @deprecated 使用 enhancedDatasetService.getVersionTree() 替代
   */
  static async getDatasetVersions(datasetId: string | number): Promise<DatasetVersion[]> {
    const response = await apiClient.get<DatasetVersion[]>(`/api/v1/datasets/${datasetId}/versions`);
    return response;
  }

  /**
   * 创建数据集版本
   * @deprecated 使用 enhancedDatasetService.createDatasetVersion() 替代
   */
  static async createDatasetVersion(
    datasetId: string | number,
    data: CreateDatasetVersionRequest
  ): Promise<DatasetVersion> {
    const response = await apiClient.post<DatasetVersion>(
      `/api/v1/datasets/${datasetId}/versions`,
      data
    );
    return response;
  }

  /**
   * 获取数据集统计信息
   */
  static async getDatasetStats(): Promise<DatasetStats> {
    const response = await apiClient.get<DatasetStats>('/api/v1/datasets/stats');
    return response;
  }

  /**
   * 搜索数据集（便捷方法）
   */
  static async searchDatasets(
    searchQuery: string,
    options?: Omit<DatasetQueryParams, 'search'>
  ): Promise<DatasetListResponse> {
    return this.getDatasets({
      search: searchQuery,
      ...options,
    });
  }

  /**
   * 获取热门数据集
   */
  static async getTrendingDatasets(
    page: number = 1,
    per_page: number = 20
  ): Promise<DatasetListResponse> {
    return this.getDatasets({
      sort_by: 'trending',
      page,
      per_page,
    });
  }

  /**
   * 获取最新数据集
   */
  static async getNewestDatasets(
    page: number = 1,
    per_page: number = 20
  ): Promise<DatasetListResponse> {
    return this.getDatasets({
      sort_by: 'newest',
      page,
      per_page,
    });
  }

  /**
   * 根据任务类型获取数据集
   */
  static async getDatasetsByTaskType(
    taskType: string,
    page: number = 1,
    per_page: number = 20
  ): Promise<DatasetListResponse> {
    return this.getDatasets({
      task_type: taskType,
      page,
      per_page,
    });
  }

  /**
   * 获取推荐数据集
   */
  static async getFeaturedDatasets(
    page: number = 1,
    per_page: number = 20
  ): Promise<DatasetListResponse> {
    return this.getDatasets({
      featured: true,
      page,
      per_page,
    });
  }

  /**
   * 获取数据集导入状态
   */
  static async getDatasetImportStatus(datasetId: string | number): Promise<DatasetImportStatus> {
    const response = await apiClient.get<DatasetImportStatus>(`/api/v1/datasets/${datasetId}/import-status`);
    return response;
  }
}

// 导出单例实例
export const datasetService = DatasetService; 