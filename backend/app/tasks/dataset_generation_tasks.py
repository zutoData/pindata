import os
import tempfile
import logging
import time
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from celery import Task
from flask import current_app
from werkzeug.datastructures import FileStorage

from app.celery_app import celery
from app.db import db
from app.models import (
    Dataset, Task as TaskModel, TaskStatus, TaskType,
    LLMConfig
)
from app.models.dataset_version import EnhancedDatasetVersion, EnhancedDatasetFile, VersionType
from app.services.storage_service import storage_service
from app.services.enhanced_dataset_service import EnhancedDatasetService
from app.services.llm_conversion_service import llm_conversion_service

logger = logging.getLogger(__name__)

def _get_llm_config_from_db(model_config_dict: Dict) -> LLMConfig:
    """从数据库获取LLM配置对象"""
    if not model_config_dict or 'id' not in model_config_dict:
        raise ValueError("模型配置字典无效或缺少'id'键")
    
    llm_config_id = model_config_dict['id']
    llm_config = LLMConfig.query.get(llm_config_id)
    
    if not llm_config:
        raise ValueError(f"在数据库中未找到ID为 {llm_config_id} 的LLM配置")
        
    logger.info(f"成功从数据库加载LLM配置: {llm_config.name} (Provider: {llm_config.provider.value})")
    return llm_config

class DatasetGenerationTask(Task):
    """数据集生成任务基类"""
    _flask_app = None

    @property
    def flask_app(self):
        if self._flask_app is None:
            from app import create_app
            self._flask_app = create_app()
        return self._flask_app

@celery.task(base=DatasetGenerationTask, bind=True, name='tasks.generate_dataset')
def generate_dataset_task(
    self, 
    dataset_id: int,
    selected_files: List[Dict],
    dataset_config: Dict,
    model_config: Dict,
    processing_config: Dict,
    task_id: int
):
    """
    自动生成数据集的Celery任务
    
    Args:
        dataset_id: 数据集ID
        selected_files: 选中的文件列表
        dataset_config: 数据集配置
        model_config: AI模型配置
        processing_config: 处理配置
        task_id: 关联的任务ID
    """
    with self.flask_app.app_context():
        start_time = time.time()
        task = None
        dataset = None
        
        try:
            logger.info(f"开始生成数据集: dataset_id={dataset_id}, 文件数量={len(selected_files)}")
            
            # 获取任务和数据集对象
            task = TaskModel.query.get(task_id)
            dataset = Dataset.query.get(dataset_id)
            
            if not task or not dataset:
                raise Exception(f"任务或数据集不存在: task_id={task_id}, dataset_id={dataset_id}")
            
            # 更新任务状态为运行中
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.progress = 0
            db.session.commit()
            
            # 更新Celery任务状态
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': 0,
                    'total': len(selected_files),
                    'status': '开始生成数据集...',
                    'dataset_name': dataset.name,
                    'current_file': None,
                    'processed_files': 0,
                    'generated_entries': 0
                }
            )
            
            # 创建数据集版本
            version = _create_dataset_version(dataset, dataset_config)
            logger.info(f"创建数据集版本: {version.id}")
            
            # 逐个处理文件
            processed_files = 0
            total_generated_entries = 0
            conversion_results = []
            
            for file_data in selected_files:
                try:
                    file_result = _process_single_file(
                        self, file_data, version, model_config, 
                        processing_config, processed_files, len(selected_files)
                    )
                    
                    conversion_results.append(file_result)
                    total_generated_entries += file_result.get('generated_entries', 0)
                    processed_files += 1
                    
                    # 更新进度
                    progress = int((processed_files / len(selected_files)) * 100)
                    task.progress = progress
                    db.session.commit()
                    
                    # 更新Celery状态
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': processed_files,
                            'total': len(selected_files),
                            'status': f'已处理 {processed_files}/{len(selected_files)} 个文件',
                            'dataset_name': dataset.name,
                            'current_file': file_result.get('filename'),
                            'processed_files': processed_files,
                            'generated_entries': total_generated_entries,
                            'progress': progress
                        }
                    )
                    
                    logger.info(f"文件处理完成: {file_result.get('filename')}, "
                              f"生成条目: {file_result.get('generated_entries', 0)}")
                    
                except Exception as file_error:
                    logger.error(f"处理文件失败: {file_data.get('name', 'unknown')}, 错误: {str(file_error)}")
                    # 继续处理其他文件，但记录错误
                    conversion_results.append({
                        'filename': file_data.get('name', 'unknown'),
                        'status': 'failed',
                        'error': str(file_error),
                        'generated_entries': 0
                    })
                    processed_files += 1
            
            # 计算成功文件数和失败率
            successful_files = len([r for r in conversion_results if r.get('status') == 'success'])
            failed_files = len([r for r in conversion_results if r.get('status') == 'failed'])
            file_success_rate = (successful_files / len(selected_files)) * 100 if selected_files else 0
            
            logger.info(f"文件处理统计: 总数={len(selected_files)}, 成功={successful_files}, "
                       f"失败={failed_files}, 成功率={file_success_rate:.1f}%")
            
            # 检查文件级别的失败率
            if file_success_rate < 50.0:
                error_msg = f"文件处理成功率过低: {file_success_rate:.1f}%，可能是LLM服务不可用或配置错误"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查是否生成了足够的数据
            if total_generated_entries == 0:
                error_msg = "未从任何文件生成数据，请检查LLM服务状态和配置"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # 如果成功率较低但不是完全失败，给出警告
            if file_success_rate < 80.0:
                warning_msg = f"注意：文件处理成功率较低({file_success_rate:.1f}%)，建议检查LLM服务状态"
                logger.warning(warning_msg)
            
            # 更新版本统计信息
            _update_version_stats(version, conversion_results, total_generated_entries)
            
            # 完成任务
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.progress = 100
            
            total_duration = time.time() - start_time
            
            result = {
                'success': True,
                'dataset_id': dataset_id,
                'version_id': version.id,
                'processed_files': processed_files,
                'total_generated_entries': total_generated_entries,
                'duration': total_duration,
                'conversion_results': conversion_results
            }
            
            task.result = result
            db.session.commit()
            
            logger.info(f"数据集生成完成: {dataset.name}, 耗时: {total_duration:.2f}秒, "
                       f"处理文件: {processed_files}, 生成条目: {total_generated_entries}")
            
            # 最终状态更新
            self.update_state(
                state='SUCCESS',
                meta={
                    'current': processed_files,
                    'total': len(selected_files),
                    'status': '数据集生成完成',
                    'dataset_name': dataset.name,
                    'duration': total_duration,
                    'generated_entries': total_generated_entries,
                    'result': result
                }
            )
            
            return result
            
        except Exception as e:
            error_message = str(e)
            total_duration = time.time() - start_time
            
            logger.error(f"数据集生成失败: {dataset_id}, 错误: {error_message}, "
                        f"耗时: {total_duration:.2f}秒")
            
            # 更新任务失败状态
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_message
                task.completed_at = datetime.utcnow()
                try:
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f"更新任务失败状态时出错: {str(commit_error)}")
            
            raise Exception(error_message)

def _create_dataset_version(dataset: Dataset, dataset_config: Dict) -> EnhancedDatasetVersion:
    """创建数据集版本"""
    try:
        # 生成版本ID和提交哈希
        version_id = str(uuid.uuid4())
        commit_hash = hashlib.sha256(f"{dataset.id}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8]
        
        # 确定版本号
        existing_versions = EnhancedDatasetVersion.query.filter_by(dataset_id=dataset.id).count()
        version_number = f"v1.{existing_versions}"
        
        # 创建版本
        version = EnhancedDatasetVersion(
            id=version_id,
            dataset_id=dataset.id,
            version=version_number,
            version_type=VersionType.MINOR,
            commit_hash=commit_hash,
            commit_message=f"自动生成数据集 - {dataset_config.get('type', 'unknown')}类型",
            author=dataset.owner,
            pipeline_config={
                'generation_method': 'smart_creator',
                'dataset_config': dataset_config,
                'generated_at': datetime.utcnow().isoformat()
            },
            is_default=existing_versions == 0  # 如果是第一个版本，设为默认
        )
        
        db.session.add(version)
        db.session.flush()
        
        logger.info(f"创建数据集版本: {version.id}, 版本号: {version_number}")
        return version
        
    except Exception as e:
        logger.error(f"创建数据集版本失败: {str(e)}")
        raise

def _process_single_file(
    celery_task, 
    file_data: Dict, 
    version: EnhancedDatasetVersion, 
    model_config_dict: Dict,
    processing_config: Dict,
    current_index: int,
    total_files: int
) -> Dict[str, Any]:
    """处理单个文件，生成数据集条目"""
    start_time = time.time()
    filename = file_data.get('name', f"file_{current_index+1}")
    logger.info(f"开始处理文件: {filename}")

    try:
        # 从数据库加载LLM配置
        llm_config = _get_llm_config_from_db(model_config_dict)

        # 更新Celery状态
        celery_task.update_state(
            state='PROGRESS',
            meta={
                'current': current_index,
                'total': total_files,
                'status': f'正在处理文件: {filename}',
                'current_file': filename,
                'stage': 'reading_file'
            }
        )
        
        # 1. 读取文件内容
        file_content = _get_file_content(file_data)
        if not file_content:
            raise Exception("无法读取文件内容")
        
        logger.info(f"文件内容长度: {len(file_content)} 字符")
        
        # 2. 根据数据集类型进行不同的处理
        dataset_type = processing_config.get('dataset_type')
        
        generation_functions = {
            'qa': _generate_qa_data,
            'summarization': _generate_summary_data,
            'instruction': _generate_instruction_data,
            'classification': _generate_classification_data,
            'generic': _generate_generic_data,
            'pretraining-data-cleaning': _generate_pretraining_cleaning_data
        }
        
        generation_func = generation_functions.get(dataset_type)
        
        if not generation_func:
            raise ValueError(f"不支持的数据集类型: {dataset_type}")
        
        # 执行生成
        generated_data = generation_func(
            content=file_content,
            llm_config=llm_config,  # 传递DB对象
            processing_config=processing_config
        )
        
        if not generated_data:
            raise Exception(f"文件 {filename} 未生成任何有效数据，可能是LLM服务不可用或内容无法处理")
        
        logger.info(f"文件 {filename} 成功生成 {len(generated_data)} 个数据条目")
        
        # 3. 保存生成的数据文件
        celery_task.update_state(
            state='PROGRESS',
            meta={
                'current': current_index,
                'total': total_files,
                'status': f'正在保存生成数据: {filename}',
                'current_file': filename,
                'stage': 'saving_data'
            }
        )
        
        dataset_file = _save_generated_data(version, filename, generated_data, file_data, processing_config)
        
        result = {
            'filename': filename,
            'status': 'success',
            'generated_entries': len(generated_data),
            'file_id': dataset_file.id,
            'file_size': dataset_file.file_size
        }
        
        logger.info(f"文件处理完成: {filename}, 生成条目: {len(generated_data)}")
        return result
        
    except Exception as e:
        logger.error(f"处理文件失败: {filename}, 错误: {str(e)}")
        raise

def _get_file_content(file_data: Dict) -> str:
    """从存储服务获取文件内容"""
    converted_object_name = file_data.get('originalFile', {}).get('converted_object_name')
    if not converted_object_name:
        raise ValueError("文件数据中缺少 'converted_object_name'")

    logger.info(f"准备从存储服务获取文件内容: {converted_object_name}")
    
    try:
        # 正确的 Bucket 名称是 'datasets'
        bucket_name = 'datasets'
        # converted_object_name 是完整的对象键
        object_name = converted_object_name
        
        logger.info(f"使用 Bucket: '{bucket_name}', Object Name: '{object_name}'")

        # 修正参数顺序：第一个参数是 object_name，第二个参数是 bucket_name
        file_bytes = storage_service.get_file(object_name, bucket_name)
        
        content = file_bytes.decode('utf-8')
        logger.info(f"文件内容加载成功，长度: {len(content)} 字符")
        return content
    except Exception as e:
        logger.error(f"获取文件失败: {str(e)}")
        raise Exception(f"文件获取失败: {str(e)}")

def _generate_qa_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """为指定内容生成问答对数据"""
    start_time = time.time()
    logger.info("开始生成QA数据...")
    
    # 准备块和配置
    chunk_size = processing_config.get('chunk_size', 2000)
    chunks = _split_content_into_chunks(content, chunk_size)
    qa_pairs_per_chunk = processing_config.get('qa_pairs_per_chunk', 5)
    
    all_qa_pairs = []
    
    # 获取LLM客户端
    llm = llm_conversion_service.get_llm_client(llm_config)
    
    for i, chunk in enumerate(chunks):
        logger.info(f"处理QA块 {i+1}/{len(chunks)}")
        
        prompt = _build_qa_generation_prompt(chunk, {
            'qa_pairs': qa_pairs_per_chunk,
            'custom_prompt': processing_config.get('custom_prompt', '')
        })
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            parsed_pairs = _parse_qa_response(response.content)
            all_qa_pairs.extend(parsed_pairs)
            logger.info(f"块 {i+1} 生成了 {len(parsed_pairs)} 个QA对")
        except Exception as e:
            logger.error(f"处理QA块 {i+1} 失败: {str(e)}")
            continue
    
    total_duration = time.time() - start_time
    logger.info(f"QA数据生成完成 - 总共: {len(all_qa_pairs)} 对, 耗时: {total_duration:.2f} 秒")
    
    return _standardize_qa_format(all_qa_pairs)

def _generate_summary_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """为指定内容生成摘要数据"""
    start_time = time.time()
    logger.info("开始生成摘要数据...")

    chunk_size = processing_config.get('chunk_size', 10000)
    chunks = _split_content_into_chunks(content, chunk_size)
    summary_length = processing_config.get('summary_length', 'medium')
    
    all_summaries = []
    llm = llm_conversion_service.get_llm_client(llm_config)

    for i, chunk in enumerate(chunks):
        logger.info(f"处理摘要块 {i+1}/{len(chunks)}")
        
        prompt = _build_summary_generation_prompt(chunk, {
            'length': summary_length,
            'custom_prompt': processing_config.get('custom_prompt', '')
        })

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            parsed_summaries = _parse_summary_response(response.content, original_text=chunk)
            all_summaries.extend(parsed_summaries)
            logger.info(f"块 {i+1} 生成了 {len(parsed_summaries)} 条摘要")
        except Exception as e:
            logger.error(f"处理摘要块 {i+1} 失败: {str(e)}")
            continue
    
    total_duration = time.time() - start_time
    logger.info(f"摘要数据生成完成 - 总共: {len(all_summaries)} 条, 耗时: {total_duration:.2f} 秒")
    
    return all_summaries

def _generate_instruction_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """为指定内容生成指令数据"""
    start_time = time.time()
    logger.info("开始生成指令数据...")

    chunk_size = processing_config.get('chunk_size', 2000)
    chunks = _split_content_into_chunks(content, chunk_size)
    instructions_per_chunk = processing_config.get('instructions_per_chunk', 3)
    
    all_instructions = []
    llm = llm_conversion_service.get_llm_client(llm_config)

    for i, chunk in enumerate(chunks):
        logger.info(f"处理指令块 {i+1}/{len(chunks)}")
        
        prompt = _build_instruction_generation_prompt(chunk, {
            'num_instructions': instructions_per_chunk,
            'custom_prompt': processing_config.get('custom_prompt', '')
        })

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            parsed_instructions = _parse_instruction_response(response.content)
            all_instructions.extend(parsed_instructions)
            logger.info(f"块 {i+1} 生成了 {len(parsed_instructions)} 条指令")
        except Exception as e:
            logger.error(f"处理指令块 {i+1} 失败: {str(e)}")
            continue
            
    total_duration = time.time() - start_time
    logger.info(f"指令数据生成完成 - 总共: {len(all_instructions)} 条, 耗时: {total_duration:.2f} 秒")
    
    return _standardize_instruction_format(all_instructions)

def _generate_classification_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """为指定内容生成分类数据"""
    start_time = time.time()
    logger.info("开始生成分类数据...")

    chunk_size = processing_config.get('chunk_size', 2000)
    chunks = _split_content_into_chunks(content, chunk_size)
    categories = processing_config.get('categories', [])

    if not categories:
        raise ValueError("分类任务需要提供 'categories' 配置")

    all_classifications = []
    llm = llm_conversion_service.get_llm_client(llm_config)

    for i, chunk in enumerate(chunks):
        logger.info(f"处理分类块 {i+1}/{len(chunks)}")
        
        prompt = _build_classification_generation_prompt(chunk, {
            'categories': categories,
            'custom_prompt': processing_config.get('custom_prompt', '')
        })

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            parsed_classifications = _parse_classification_response(response.content)
            all_classifications.extend(parsed_classifications)
            logger.info(f"块 {i+1} 生成了 {len(parsed_classifications)} 条分类")
        except Exception as e:
            logger.error(f"处理分类块 {i+1} 失败: {str(e)}")
            continue
            
    total_duration = time.time() - start_time
    logger.info(f"分类数据生成完成 - 总共: {len(all_classifications)} 条, 耗时: {total_duration:.2f} 秒")
    
    return _standardize_classification_format(all_classifications)

def _generate_generic_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """通用数据生成/处理"""
    start_time = time.time()
    logger.info("开始通用数据生成...")

    chunk_size = processing_config.get('chunk_size', 2000)
    chunks = _split_content_into_chunks(content, chunk_size)
    custom_prompt = processing_config.get('custom_prompt')

    if not custom_prompt:
        raise ValueError("通用任务需要提供 'custom_prompt' (自定义提示词)")

    all_results = []
    llm = llm_conversion_service.get_llm_client(llm_config)

    for i, chunk in enumerate(chunks):
        logger.info(f"处理通用块 {i+1}/{len(chunks)}")
        
        prompt = _build_custom_prompt_for_chunk(chunk, custom_prompt, processing_config)
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            parsed_data = _parse_generic_response(response.content)
            all_results.extend(parsed_data)
            logger.info(f"块 {i+1} 生成了 {len(parsed_data)} 条数据")
        except Exception as e:
            logger.error(f"处理通用块 {i+1} 失败: {str(e)}")
            continue
            
    total_duration = time.time() - start_time
    logger.info(f"通用数据生成完成 - 总共: {len(all_results)} 条, 耗时: {total_duration:.2f} 秒")
    
    return all_results

def _generate_pretraining_cleaning_data(content: str, llm_config: LLMConfig, processing_config: Dict) -> List[Dict]:
    """为预训练任务清洗数据"""
    start_time = time.time()
    logger.info("开始清洗预训练数据...")

    # 对于预训练数据清洗，使用maxDocumentLength进行分块
    max_document_length = processing_config.get('maxDocumentLength', 50000)
    
    # 如果文档长度超过限制，按maxDocumentLength分块处理
    if len(content) > max_document_length:
        logger.info(f"文档长度 {len(content)} 超过限制 {max_document_length}，按块处理")
        chunks = _split_content_into_chunks(content, max_document_length)
        logger.info(f"文档被分为 {len(chunks)} 个块进行处理")
    else:
        # 如果文档长度在限制内，直接处理整个文档
        chunks = [content]
    
    if not chunks:
        logger.warning("内容分块后为空，无法进行清洗")
        return []
        
    logger.info(f"内容被分为 {len(chunks)} 个块进行处理")

    # 使用LLM服务进行清洗
    llm_response = llm_conversion_service.batch_convert_text(
        chunks=chunks,
        model_config=llm_config.to_dict(), # 传递DB对象的字典表示
        conversion_type='pretraining-cleaning',
        processing_config=processing_config
    )

    if llm_response.get('status') != 'success':
        error_msg = llm_response.get('error', '未知的LLM服务错误')
        logger.error(f"预训练数据清洗失败: {error_msg}")
        raise Exception(f"LLM服务调用失败: {error_msg}")
    
    all_cleaned_data = []
    
    # 解析LLM返回的每个块的结果
    for i, result_chunk in enumerate(llm_response.get('chunks', [])):
        if result_chunk.get('status') == 'success':
            cleaned_content = result_chunk.get('cleaned_content', '')
            parsed_data = _parse_pretraining_cleaning_response(cleaned_content, i)
            all_cleaned_data.extend(parsed_data)
        else:
            # 如果LLM处理失败，可以采用备用方案，例如基础清洗
            logger.warning(f"块 {i+1} LLM清洗失败: {result_chunk.get('error')}. "
                           "将使用基础清洗作为备用。")
            original_chunk = result_chunk.get('original_content', '')
            basic_cleaned_data = _basic_text_cleaning(original_chunk, i)
            all_cleaned_data.extend(basic_cleaned_data)
            
    total_duration = time.time() - start_time
    logger.info(f"预训练数据清洗完成 - 总共生成: {len(all_cleaned_data)} 条数据, "
               f"耗时: {total_duration:.2f} 秒")

    return all_cleaned_data

def _estimate_processing_time(content_length: int, use_llm: bool = False) -> Dict[str, float]:
    """估算处理时间"""
    # 基于经验值：平均每1000字符需要约2-5秒LLM处理时间
    chars_per_second = 200  # 保守估计
    base_processing_seconds = content_length / chars_per_second
    
    # 考虑网络延迟和其他开销，增加50%缓冲
    total_seconds = base_processing_seconds * 1.5
    
    if use_llm:
        # 如果使用LLM，增加额外的时间
        llm_processing_seconds = base_processing_seconds * 0.5
        total_seconds += llm_processing_seconds
    
    return {
        'total_seconds': total_seconds,
        'total_minutes': total_seconds / 60,
        'total_hours': total_seconds / 3600,
        'estimated_chunks': max(1, content_length // 50000),
        'time_per_chunk': total_seconds / content_length if content_length > 0 else 0
    }

def _calculate_dynamic_timeout(chunk_text: str, chunk_index: int, total_chunks: int) -> int:
    """根据块特征动态计算超时时间 - 简化版本"""
    text_length = len(chunk_text)
    
    # 简化的超时时间计算 - 主要防止API完全无响应
    if text_length > 50000:
        timeout = 1800  # 30分钟 - 处理超长文本
    elif text_length > 20000:
        timeout = 900   # 15分钟 - 处理长文本
    else:
        timeout = 600   # 10分钟 - 处理普通文本
    
    # 对于长文档（超过100块），给予更宽松的超时时间
    if total_chunks > 100:
        timeout = int(timeout * 1.5)
    
    return timeout

def _build_pretraining_cleaning_prompt(chunk: str, config: Dict) -> str:
    """构建预训练数据清洗提示词 - 返回特定格式的语料数据"""
    prompt = f"""你是一个专业的预训练数据清洗助理。你的任务是将原始文本清洗成适合大语言模型预训练的高质量语料。

请按照以下要求清洗文本：

1. **内容清洗**：
   - 去除markdown标记、HTML标签、多余的空行和空格
   - 去除无意义的重复内容和噪声文本
   - 保留有价值的信息和完整的句子
   - 确保语言自然流畅

2. **格式要求**：
   - 每个清洗后的语料段落必须用以下格式包裹：[语料开始]...[语料结束]
   - 如果有多个独立的语料段落，每个都要单独包裹
   - 语料内容要保证句子完整，段落逻辑清晰

3. **质量标准**：
   - 语料长度至少30个字符
   - 内容要有实际价值，避免纯标题或目录
   - 保持原文的语言风格和专业性

原始文本：
{chunk}

请严格按照上述要求处理，并将每个清洗后的语料用[语料开始]和[语料结束]标记包裹。

清洗结果："""
    
    return prompt

def _parse_pretraining_cleaning_response(response: str, chunk_index: int) -> List[Dict]:
    """解析预训练数据清洗响应 - 输出完整的清洗后语料"""
    try:
        if not response or not response.strip():
            return []
        
        # 使用正则表达式提取[语料开始]和[语料结束]之间的内容
        import re
        
        # 匹配[语料开始]...[语料结束]的内容
        pattern = r'\[语料开始\](.*?)\[语料结束\]'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if not matches:
            # 如果没有找到标记，尝试其他可能的变体
            alt_patterns = [
                r'\[语料开始\](.*?)\[语料结束\]',
                r'语料开始](.*?)\[语料结束',
                r'\[语料开始(.*?)语料结束\]',
                r'语料开始(.*?)语料结束'
            ]
            
            for alt_pattern in alt_patterns:
                matches = re.findall(alt_pattern, response, re.DOTALL)
                if matches:
                    break
            
            # 如果还是没有找到，回退到传统解析方式
            if not matches:
                logger.warning(f"未找到语料标记，使用传统解析方式处理")
                return _parse_pretraining_cleaning_response_fallback(response, chunk_index)
        
        # 对于预训练数据清洗，将所有提取的语料片段合并成一个完整的语料
        if matches:
            # 清理并合并所有提取的内容
            cleaned_segments = []
            for match in matches:
                # 清理提取的内容
                cleaned_content = match.strip()
                # 移除可能的多余空白和换行
                cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
                cleaned_content = re.sub(r'\n\s*\n', '\n\n', cleaned_content)
                
                if len(cleaned_content) >= 30:  # 确保内容长度足够
                    cleaned_segments.append(cleaned_content)
            
            if cleaned_segments:
                # 将所有语料片段合并成一个完整的语料
                full_corpus = '\n\n'.join(cleaned_segments)
                
                result = [{
                    'id': 'doc_1',
                    'text': full_corpus,
                    'source': 'llm_cleaned',
                    'type': 'corpus_text',
                    'length': len(full_corpus),
                    'chunk_index': 0,
                    'segment_index': 0,
                    'quality_score': min(1.0, len(full_corpus) / 1000.0),  # 基于长度的质量分数
                    'segments_count': len(cleaned_segments)
                }]
                
                logger.info(f"成功提取并合并了{len(cleaned_segments)}个语料片段，总长度: {len(full_corpus)}")
                return result
        
        logger.warning("语料内容质量不足，使用回退方式")
        return _parse_pretraining_cleaning_response_fallback(response, chunk_index)
        
    except Exception as e:
        logger.error(f"解析预训练清洗响应失败: {str(e)}")
        return _parse_pretraining_cleaning_response_fallback(response, chunk_index)

def _parse_pretraining_cleaning_response_fallback(response: str, chunk_index: int) -> List[Dict]:
    """解析预训练数据清洗响应的回退方法 - 输出完整的清洗后语料"""
    try:
        import re
        
        if not response or not response.strip():
            return []
        
        # 清理响应文本
        cleaned_text = response.strip()
        
        # 如果响应包含解释性文字，尝试提取纯文本
        if "清洗后的文本" in cleaned_text or "输出" in cleaned_text or "清洗结果" in cleaned_text:
            lines = cleaned_text.split('\n')
            text_lines = []
            start_collecting = False
            
            for line in lines:
                if any(keyword in line for keyword in ["清洗后", "输出", "结果", "清洗结果"]) and ":" in line:
                    start_collecting = True
                    # 如果这行冒号后面有内容，也要包含
                    if line.split(':', 1)[1].strip():
                        text_lines.append(line.split(':', 1)[1].strip())
                elif start_collecting:
                    text_lines.append(line)
            
            if text_lines:
                cleaned_text = '\n'.join(text_lines).strip()
        
        # 清理可能的AI回复格式
        cleaned_text = re.sub(r'^(好的|当然|我来|我将|让我)+[，。]*', '', cleaned_text)
        cleaned_text = re.sub(r'(以上|以下|如上|如下)+[是为].+[：:]\s*', '', cleaned_text)
        
        # 最终清理
        cleaned_text = cleaned_text.strip()
        
        # 对于预训练数据清洗，输出一个完整的清洗后语料
        if len(cleaned_text) >= 30:  # 确保内容长度足够
            result = [{
                'id': 'doc_1',
                'text': cleaned_text,
                'source': 'llm_cleaned_fallback',
                'type': 'corpus_text',
                'length': len(cleaned_text),
                'chunk_index': 0,
                'segment_index': 0,
                'quality_score': min(1.0, len(cleaned_text) / 1000.0)  # 基于长度的质量分数
            }]
            
            logger.info(f"回退解析成功，生成完整语料，长度: {len(cleaned_text)}")
            return result
        else:
            logger.warning("回退解析后内容长度不足")
            return []
        
    except Exception as e:
        logger.error(f"回退解析失败: {str(e)}")
        return []

def _basic_text_cleaning(chunk: str, chunk_index: int) -> List[Dict]:
    """基础文本清洗（不使用LLM）- 输出完整的清洗后语料"""
    try:
        import re
        
        text = chunk.strip()
        
        # 基础清洗规则
        # 1. 去除markdown标题
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # 2. 去除markdown粗体和斜体
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # 3. 去除markdown代码块
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # 4. 去除markdown链接
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # 5. 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 6. 去除多余空格和空行
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 7. 去除行首行尾空格
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        # 8. 去除特殊符号和噪声
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,!?;:(){}[\]"\'""''—–-]', '', text)
        
        # 9. 清理重复的标点符号
        text = re.sub(r'[。！？]{2,}', '。', text)
        text = re.sub(r'[，、]{2,}', '，', text)
        
        # 10. 确保段落间的适当空格
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # 最终清理
        text = text.strip()
        
        # 对于预训练数据清洗，输出一个完整的清洗后语料
        if len(text) >= 30:  # 确保语料长度足够
            result = [{
                'id': 'doc_1',
                'text': text,
                'source': 'basic_cleaned',
                'type': 'corpus_text',
                'length': len(text),
                'chunk_index': 0,
                'segment_index': 0,
                'quality_score': min(1.0, len(text) / 1000.0)  # 基于长度的质量分数
            }]
            
            logger.info(f"基础清洗完成，生成完整语料，长度: {len(text)}")
            return result
        else:
            logger.warning("基础清洗后内容长度不足，跳过")
            return []
        
    except Exception as e:
        logger.error(f"基础清洗失败: {str(e)}")
        return []

def _parse_generic_response(response: str) -> List[Dict]:
    """解析通用响应"""
    try:
        import json
        import re
        
        # 尝试解析JSON
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        except:
            pass
        
        # 尝试提取JSON对象
        json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response)
        if json_objects:
            parsed_objects = []
            for obj_str in json_objects:
                try:
                    obj = json.loads(obj_str)
                    parsed_objects.append(obj)
                except:
                    continue
            if parsed_objects:
                return parsed_objects
        
        return []
        
    except Exception as e:
        logger.error(f"解析通用响应失败: {str(e)}")
        return []

def _split_content_into_chunks(content: str, chunk_size: int) -> List[str]:
    """将内容分割成块"""
    try:
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            
            # 尝试在句号处分割，避免截断句子
            if end < len(content):
                # 向后查找句号
                sentence_end = content.rfind('。', start, end)
                if sentence_end == -1:
                    sentence_end = content.rfind('.', start, end)
                if sentence_end == -1:
                    sentence_end = content.rfind('！', start, end)
                if sentence_end == -1:
                    sentence_end = content.rfind('？', start, end)
                
                if sentence_end > start:
                    end = sentence_end + 1
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
        
        return chunks
        
    except Exception as e:
        logger.error(f"分割内容失败: {str(e)}")
        return [content]  # 返回原内容作为单个块

def _split_content_into_chunks_with_overlap(content: str, chunk_size: int, overlap: int) -> List[str]:
    """将内容分割成有重叠的块"""
    try:
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            
            # 尝试在合适的位置分割，优先考虑句子边界
            if end < len(content):
                # 向后查找句号
                for delimiter in ['。', '.', '！', '？', '\n\n', '\n']:
                    sentence_end = content.rfind(delimiter, start, end)
                    if sentence_end > start:
                        end = sentence_end + len(delimiter)
                        break
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 计算下一个起始位置，考虑重叠
            start = max(start + chunk_size - overlap, end)
            
            # 避免无限循环
            if start >= len(content):
                break
        
        return chunks
        
    except Exception as e:
        logger.error(f"分割内容失败: {str(e)}")
        return [content]

def _build_custom_prompt_for_chunk(chunk: str, custom_prompt: str, processing_config: Dict) -> str:
    """为文档块构建自定义提示词"""
    try:
        # 使用前端生成的详细提示词作为基础
        base_prompt = custom_prompt
        
        # 添加文档块的具体内容
        prompt = f"{base_prompt}\n\n## 待处理文档内容\n{chunk}\n\n请严格按照上述要求处理这段文档内容。"
        
        return prompt
        
    except Exception as e:
        logger.error(f"构建自定义提示词失败: {str(e)}")
        # 回退到基础提示词
        return f"请处理以下文档内容：\n\n{chunk}"

def _build_qa_generation_prompt(content: str, config: Dict) -> str:
    """构建问答生成提示词"""
    qa_count = config.get('qa_pairs_per_chunk', 3)
    
    prompt = f"""请基于以下文本内容生成 {qa_count} 个高质量的问答对。

要求：
1. 问题应该涵盖文本的关键信息点
2. 答案应该准确、简洁且完整
3. 问题类型多样化（事实性、理解性、分析性）
4. 使用JSON格式返回

文本内容：
{content}

请按以下JSON格式返回：
[
  {{
    "question": "问题1",
    "answer": "答案1",
    "type": "factual"
  }},
  {{
    "question": "问题2", 
    "answer": "答案2",
    "type": "comprehension"
  }}
]
"""
    return prompt

def _build_summary_generation_prompt(content: str, config: Dict) -> str:
    """构建摘要生成提示词"""
    summary_length = config.get('summary_length', 'medium')
    
    length_map = {
        'short': '50-100字',
        'medium': '100-200字',
        'long': '200-400字'
    }
    
    prompt = f"""请为以下文本生成高质量的摘要。

要求：
1. 摘要长度：{length_map.get(summary_length, '100-200字')}
2. 保留关键信息和核心观点
3. 语言简洁明了
4. 使用JSON格式返回

文本内容：
{content}

请按以下JSON格式返回：
[
  {{
    "original_text": "原文内容",
    "summary": "摘要内容",
    "key_points": ["要点1", "要点2", "要点3"]
  }}
]
"""
    return prompt

def _build_instruction_generation_prompt(content: str, config: Dict) -> str:
    """构建指令生成提示词"""
    instruction_count = config.get('instructions_per_chunk', 2)
    
    prompt = f"""请基于以下文本内容生成 {instruction_count} 个指令跟随格式的训练数据。

要求：
1. 指令应该明确具体
2. 输入可选，但要与指令相关
3. 输出应该基于文本内容
4. 使用JSON格式返回

文本内容：
{content}

请按以下JSON格式返回：
[
  {{
    "instruction": "具体指令",
    "input": "输入内容（可选）",
    "output": "期望输出"
  }}
]
"""
    return prompt

def _build_classification_generation_prompt(content: str, config: Dict) -> str:
    """构建分类生成提示词"""
    categories = config.get('categories', ['positive', 'negative', 'neutral'])
    
    prompt = f"""请为以下文本内容生成分类训练数据。

可选分类：{', '.join(categories)}

要求：
1. 为文本片段分配合适的分类标签
2. 提供分类理由
3. 使用JSON格式返回

文本内容：
{content}

请按以下JSON格式返回：
[
  {{
    "text": "文本片段",
    "label": "分类标签",
    "confidence": 0.95,
    "reason": "分类理由"
  }}
]
"""
    return prompt

def _parse_qa_response(response: str, dataset_type: str = None) -> List[Dict]:
    """解析问答响应"""
    try:
        import json
        import re
        
        # 清理响应内容
        response = response.strip()
        
        # 尝试直接解析JSON
        try:
            qa_pairs = json.loads(response)
            if isinstance(qa_pairs, list):
                return _standardize_qa_format(qa_pairs, dataset_type)
        except:
            pass
        
        # 尝试提取JSON数组
        json_array_pattern = r'\[.*?\]'
        json_matches = re.findall(json_array_pattern, response, re.DOTALL)
        for match in json_matches:
            try:
                qa_pairs = json.loads(match)
                if isinstance(qa_pairs, list) and len(qa_pairs) > 0:
                    return _standardize_qa_format(qa_pairs, dataset_type)
            except:
                continue
        
        # 尝试提取多个JSON对象
        # 改进的正则表达式，可以匹配多个独立的JSON对象，即使它们之间没有逗号或数组包裹
        json_object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_objects = re.findall(json_object_pattern, response)
        if json_objects:
            parsed_objects = []
            for obj_str in json_objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict):
                        parsed_objects.append(obj)
                except json.JSONDecodeError as e:
                    logger.warning(f"解析单个JSON对象失败: {obj_str[:100]}..., 错误: {e}")
                    continue
            if parsed_objects:
                logger.info(f"成功从响应中提取 {len(parsed_objects)} 个JSON对象")
                return _standardize_qa_format(parsed_objects, dataset_type)
        
        # 尝试基于模式匹配提取问答对
        qa_pairs = _extract_qa_pairs_from_text(response)
        if qa_pairs:
            return _standardize_qa_format(qa_pairs, dataset_type)
        
        # 记录失败信息用于调试
        logger.warning(f"无法解析问答响应，响应内容前500字符: {response[:500]}")
        return []
        
    except Exception as e:
        logger.error(f"解析问答响应失败: {str(e)}")
        return []

def _standardize_qa_format(qa_pairs: List[Dict], dataset_type: str = None) -> List[Dict]:
    """标准化问答对格式"""
    standardized = []
    
    for qa in qa_pairs:
        if not isinstance(qa, dict):
            continue
        
        # 提取问题和答案，支持多种字段名
        question = qa.get('question') or qa.get('q') or qa.get('instruction') or qa.get('prompt', '')
        answer = qa.get('answer') or qa.get('a') or qa.get('output') or qa.get('response', '')
        
        if question and answer:
            # 根据数据集类型标准化格式
            if dataset_type == 'instruction-tuning':
                standardized_qa = {
                    'instruction': question,
                    'input': qa.get('input', ''),
                    'output': answer,
                    'type': qa.get('type', 'instruction')
                }
            else:
                # 默认问答对格式
                standardized_qa = {
                    'question': question,
                    'answer': answer,
                    'type': qa.get('type', 'qa')
                }
            
            # 添加额外的元数据
            if 'confidence' in qa:
                standardized_qa['confidence'] = qa['confidence']
            if 'category' in qa:
                standardized_qa['category'] = qa['category']
            
            standardized.append(standardized_qa)
    
    return standardized

def _extract_qa_pairs_from_text(text: str) -> List[Dict]:
    """从文本中提取问答对"""
    import re
    
    qa_pairs = []
    
    # 模式1: Q: ... A: ... 格式
    pattern1 = r'Q[:\s]*(.+?)\s*A[:\s]*(.+?)(?=Q:|$)'
    matches1 = re.findall(pattern1, text, re.DOTALL | re.IGNORECASE)
    for question, answer in matches1:
        qa_pairs.append({
            'question': question.strip(),
            'answer': answer.strip(),
            'type': 'extracted'
        })
    
    # 模式2: 问: ... 答: ... 格式
    pattern2 = r'问[:\s]*(.+?)\s*答[:\s]*(.+?)(?=问:|$)'
    matches2 = re.findall(pattern2, text, re.DOTALL)
    for question, answer in matches2:
        qa_pairs.append({
            'question': question.strip(),
            'answer': answer.strip(),
            'type': 'extracted'
        })
    
    return qa_pairs

def _parse_summary_response(response: str, original_text: str) -> List[Dict]:
    """解析摘要响应"""
    try:
        import json
        
        try:
            summary_data = json.loads(response)
            if isinstance(summary_data, list):
                return summary_data
        except:
            pass
        
        # 简单解析，如果JSON解析失败
        return [{
            'original_text': original_text[:200] + '...' if len(original_text) > 200 else original_text,
            'summary': response.strip(),
            'key_points': []
        }]
        
    except Exception as e:
        logger.error(f"解析摘要响应失败: {str(e)}")
        return []

def _parse_instruction_response(response: str, dataset_type: str = None) -> List[Dict]:
    """解析指令响应"""
    try:
        import json
        import re
        
        # 清理响应内容
        response = response.strip()
        
        # 尝试直接解析JSON
        try:
            instruction_data = json.loads(response)
            if isinstance(instruction_data, list):
                return _standardize_instruction_format(instruction_data, dataset_type)
        except:
            pass
        
        # 尝试提取JSON数组
        json_array_pattern = r'\[.*?\]'
        json_matches = re.findall(json_array_pattern, response, re.DOTALL)
        for match in json_matches:
            try:
                instruction_data = json.loads(match)
                if isinstance(instruction_data, list) and len(instruction_data) > 0:
                    return _standardize_instruction_format(instruction_data, dataset_type)
            except:
                continue
        
        # 尝试提取多个JSON对象
        json_object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_objects = re.findall(json_object_pattern, response)
        if json_objects:
            parsed_objects = []
            for obj_str in json_objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict):
                        parsed_objects.append(obj)
                except:
                    continue
            if parsed_objects:
                return _standardize_instruction_format(parsed_objects, dataset_type)
        
        # 记录实际响应内容以便调试
        logger.warning(f"无法解析指令响应，响应内容前500字符: {response[:500]}")
        return []
        
    except Exception as e:
        logger.error(f"解析指令响应失败: {str(e)}")
        return []

def _parse_classification_response(response: str, dataset_type: str = None) -> List[Dict]:
    """解析分类响应"""
    try:
        import json
        import re
        
        # 清理响应内容
        response = response.strip()
        
        # 尝试直接解析JSON
        try:
            classification_data = json.loads(response)
            if isinstance(classification_data, list):
                return _standardize_classification_format(classification_data, dataset_type)
        except:
            pass
        
        # 尝试提取JSON数组
        json_array_pattern = r'\[.*?\]'
        json_matches = re.findall(json_array_pattern, response, re.DOTALL)
        for match in json_matches:
            try:
                classification_data = json.loads(match)
                if isinstance(classification_data, list) and len(classification_data) > 0:
                    return _standardize_classification_format(classification_data, dataset_type)
            except:
                continue
        
        # 尝试提取多个JSON对象
        json_object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_objects = re.findall(json_object_pattern, response)
        if json_objects:
            parsed_objects = []
            for obj_str in json_objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict):
                        parsed_objects.append(obj)
                except:
                    continue
            if parsed_objects:
                return _standardize_classification_format(parsed_objects, dataset_type)
        
        # 记录实际响应内容以便调试
        logger.warning(f"无法解析分类响应，响应内容前500字符: {response[:500]}")
        return []
        
    except Exception as e:
        logger.error(f"解析分类响应失败: {str(e)}")
        return []

def _standardize_instruction_format(instructions: List[Dict], dataset_type: str = None) -> List[Dict]:
    """标准化指令格式"""
    standardized = []
    
    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        
        # 提取指令、输入和输出，支持多种字段名
        instruction = inst.get('instruction') or inst.get('prompt') or inst.get('task', '')
        input_text = inst.get('input') or inst.get('context') or ''
        output_text = inst.get('output') or inst.get('response') or inst.get('answer', '')
        
        if instruction and output_text:
            standardized_inst = {
                'instruction': instruction,
                'input': input_text,
                'output': output_text,
                'type': inst.get('type', 'instruction')
            }
            
            # 添加额外的元数据
            for key in ['difficulty', 'category', 'domain', 'tags']:
                if key in inst:
                    standardized_inst[key] = inst[key]
            
            standardized.append(standardized_inst)
    
    return standardized

def _standardize_classification_format(classifications: List[Dict], dataset_type: str = None) -> List[Dict]:
    """标准化分类格式"""
    standardized = []
    
    for cls in classifications:
        if not isinstance(cls, dict):
            continue
        
        # 提取文本和标签，支持多种字段名
        text = cls.get('text') or cls.get('content') or cls.get('input', '')
        label = cls.get('label') or cls.get('category') or cls.get('class', '')
        
        if text and label:
            standardized_cls = {
                'text': text,
                'label': label,
                'type': 'classification'
            }
            
            # 添加额外的元数据
            for key in ['confidence', 'reason', 'probability', 'score']:
                if key in cls:
                    standardized_cls[key] = cls[key]
            
            standardized.append(standardized_cls)
    
    return standardized

def _save_generated_data(version: EnhancedDatasetVersion, original_filename: str, 
                        generated_data: List[Dict], file_data: Dict, 
                        processing_config: Dict = None) -> EnhancedDatasetFile:
    """保存生成的数据文件"""
    try:
        import json
        import tempfile
        
        # 获取输出格式配置
        output_format = processing_config.get('output_format', 'JSONL') if processing_config else 'JSONL'
        dataset_type = processing_config.get('dataset_type', 'qa') if processing_config else 'qa'
        
        logger.info(f"准备保存数据 - 格式: {output_format}, 类型: {dataset_type}, 条目数: {len(generated_data)}")
        
        # 转换数据格式
        converted_data = _convert_to_training_format(generated_data, output_format, dataset_type)
        
        # 准备文件名和扩展名
        base_name = os.path.splitext(original_filename)[0]
        
        if output_format.upper() in ['CSV']:
            file_extension = '.csv'
            content_type = 'text/csv'
        elif output_format.upper() in ['ALPACA', 'SHAREGPT', 'OPENAI']:
            file_extension = '.jsonl'
            content_type = 'application/jsonl'
        else:
            file_extension = '.jsonl'
            content_type = 'application/jsonl'
        
        generated_filename = f"{base_name}_generated_{dataset_type}{file_extension}"
        
        # 生成文件内容
        if output_format.upper() == 'CSV':
            file_content = _generate_csv_content(converted_data)
        else:
            # JSONL格式
            file_content = '\n'.join([json.dumps(item, ensure_ascii=False) for item in converted_data])
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix=file_extension, delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name
        
        try:
            # 上传到MinIO
            object_name = f"datasets/{version.dataset_id}/{version.version}/generated/{generated_filename}"
            
            # 使用upload_file_from_path方法
            bucket_name = current_app.config.get('MINIO_DATASETS_BUCKET', 'datasets')
            file_size = storage_service.upload_file_from_path(
                tmp_file_path, object_name, content_type, bucket_name
            )
            uploaded_object = object_name
            
            # 计算文件校验和
            with open(tmp_file_path, 'rb') as f:
                checksum = hashlib.md5(f.read()).hexdigest()
            
            # 创建文件记录
            dataset_file = EnhancedDatasetFile(
                version_id=version.id,
                filename=generated_filename,
                file_path=f"datasets/{version.dataset_id}/versions/{version.id}/{generated_filename}",
                file_type='json' if file_extension == '.jsonl' else 'csv',
                file_size=file_size,
                checksum=checksum,
                minio_bucket=current_app.config.get('MINIO_DATASETS_BUCKET', 'datasets'),
                minio_object_name=uploaded_object,
                file_metadata={
                    'original_file': original_filename,
                    'generation_type': 'auto_generated',
                    'entries_count': len(converted_data),
                    'dataset_type': dataset_type,
                    'output_format': output_format,
                    'source_file_data': file_data
                },
                preview_data={
                    'type': output_format.lower(),
                    'sample_entries': converted_data[:3],  # 保存前3个条目作为预览
                    'total_entries': len(converted_data),
                    'format_info': {
                        'name': output_format,
                        'description': f'{dataset_type}类型的{output_format}格式数据',
                        'file_extension': file_extension
                    }
                }
            )
            
            db.session.add(dataset_file)
            db.session.flush()
            
            logger.info(f"保存生成数据文件: {generated_filename}, 格式: {output_format}, "
                       f"大小: {file_size} 字节, 条目数: {len(converted_data)}")
            
            return dataset_file
            
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_file_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"保存生成数据失败: {str(e)}")
        raise

def _convert_to_training_format(data: List[Dict], output_format: str, dataset_type: str) -> List[Dict]:
    """将数据转换为训练格式"""
    try:
        converted_data = []
        format_upper = output_format.upper()
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            converted_item = None
            
            if format_upper == 'ALPACA':
                converted_item = _convert_to_alpaca_format(item, dataset_type)
            elif format_upper == 'SHAREGPT':
                converted_item = _convert_to_sharegpt_format(item, dataset_type)
            elif format_upper == 'OPENAI':
                converted_item = _convert_to_openai_format(item, dataset_type)
            elif format_upper == 'CSV':
                converted_item = _convert_to_csv_format(item, dataset_type)
            else:
                # 默认保持原格式
                converted_item = item
            
            if converted_item:
                converted_data.append(converted_item)
        
        logger.info(f"格式转换完成: {output_format}, 原始条目: {len(data)}, 转换后条目: {len(converted_data)}")
        return converted_data
        
    except Exception as e:
        logger.error(f"格式转换失败: {str(e)}")
        return data  # 返回原始数据

def _convert_to_alpaca_format(item: Dict, dataset_type: str) -> Dict:
    """转换为Alpaca格式"""
    if dataset_type in ['qa-pairs', 'qa']:
        result = {
            'instruction': item.get('question', item.get('instruction', '')),
            'input': '',
            'output': item.get('answer', item.get('output', ''))
        }
        # 如果有思考过程，添加到结果中
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'instruction-tuning':
        result = {
            'instruction': item.get('instruction', ''),
            'input': item.get('input', ''),
            'output': item.get('output', '')
        }
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'text-classification':
        result = {
            'instruction': f"请对以下文本进行分类：{item.get('text', '')}",
            'input': '',
            'output': item.get('label', '')
        }
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'pretraining-data-cleaning':
        # 预训练数据清洗输出纯净语料格式
        return {
            'text': item.get('text', ''),
            'id': item.get('id', ''),
            'source': item.get('source', 'cleaned'),
            'type': item.get('type', 'corpus_text'),
            'length': item.get('length', len(item.get('text', ''))),
            'chunk_index': item.get('chunk_index', 0),
            'segment_index': item.get('segment_index', 0),
            'quality_score': item.get('quality_score', 0.0)
        }
    else:
        return item

def _convert_to_sharegpt_format(item: Dict, dataset_type: str) -> Dict:
    """转换为ShareGPT格式"""
    if dataset_type in ['qa-pairs', 'qa']:
        conversations = [
            {'role': 'user', 'content': item.get('question', item.get('instruction', ''))},
            {'role': 'assistant', 'content': item.get('answer', item.get('output', ''))}
        ]
        # 如果有思考过程，在助手回复前添加思考过程
        if 'thinking' in item and item['thinking']:
            conversations.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'conversations': conversations}
    elif dataset_type == 'instruction-tuning':
        user_content = item.get('instruction', '')
        if item.get('input'):
            user_content += f"\n\n{item.get('input')}"
        
        conversations = [
            {'role': 'user', 'content': user_content},
            {'role': 'assistant', 'content': item.get('output', '')}
        ]
        if 'thinking' in item and item['thinking']:
            conversations.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'conversations': conversations}
    elif dataset_type == 'text-classification':
        conversations = [
            {'role': 'user', 'content': f"请对以下文本进行分类：{item.get('text', '')}"},
            {'role': 'assistant', 'content': f"分类结果：{item.get('label', '')}"}
        ]
        if 'thinking' in item and item['thinking']:
            conversations.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'conversations': conversations}
    elif dataset_type == 'pretraining-data-cleaning':
        # 预训练数据清洗输出纯净语料格式（不适合对话格式，返回原格式）
        return {
            'text': item.get('text', ''),
            'id': item.get('id', ''),
            'source': item.get('source', 'cleaned'),
            'type': item.get('type', 'corpus_text'),
            'length': item.get('length', len(item.get('text', ''))),
            'chunk_index': item.get('chunk_index', 0),
            'segment_index': item.get('segment_index', 0),
            'quality_score': item.get('quality_score', 0.0)
        }
    else:
        return item

def _convert_to_openai_format(item: Dict, dataset_type: str) -> Dict:
    """转换为OpenAI格式"""
    if dataset_type in ['qa-pairs', 'qa']:
        messages = [
            {'role': 'user', 'content': item.get('question', item.get('instruction', ''))},
            {'role': 'assistant', 'content': item.get('answer', item.get('output', ''))}
        ]
        # 如果有思考过程，在助手回复前添加思考过程
        if 'thinking' in item and item['thinking']:
            messages.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'messages': messages}
    elif dataset_type == 'instruction-tuning':
        user_content = item.get('instruction', '')
        if item.get('input'):
            user_content += f"\n\n{item.get('input')}"
        
        messages = [
            {'role': 'user', 'content': user_content},
            {'role': 'assistant', 'content': item.get('output', '')}
        ]
        if 'thinking' in item and item['thinking']:
            messages.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'messages': messages}
    elif dataset_type == 'text-classification':
        messages = [
            {'role': 'user', 'content': f"请对以下文本进行分类：{item.get('text', '')}"},
            {'role': 'assistant', 'content': f"分类结果：{item.get('label', '')}"}
        ]
        if 'thinking' in item and item['thinking']:
            messages.insert(1, {'role': 'assistant', 'content': f"<thinking>\n{item['thinking']}\n</thinking>"})
        return {'messages': messages}
    elif dataset_type == 'pretraining-data-cleaning':
        # 预训练数据清洗输出纯净语料格式（不适合消息格式，返回原格式）
        return {
            'text': item.get('text', ''),
            'id': item.get('id', ''),
            'source': item.get('source', 'cleaned'),
            'type': item.get('type', 'corpus_text'),
            'length': item.get('length', len(item.get('text', ''))),
            'chunk_index': item.get('chunk_index', 0),
            'segment_index': item.get('segment_index', 0),
            'quality_score': item.get('quality_score', 0.0)
        }
    else:
        return item

def _convert_to_csv_format(item: Dict, dataset_type: str) -> Dict:
    """转换为CSV格式"""
    if dataset_type in ['qa-pairs', 'qa']:
        result = {
            'question': item.get('question', item.get('instruction', '')),
            'answer': item.get('answer', item.get('output', ''))
        }
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'instruction-tuning':
        result = {
            'instruction': item.get('instruction', ''),
            'input': item.get('input', ''),
            'output': item.get('output', '')
        }
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'text-classification':
        result = {
            'text': item.get('text', ''),
            'label': item.get('label', '')
        }
        if 'thinking' in item and item['thinking']:
            result['thinking'] = item['thinking']
        return result
    elif dataset_type == 'pretraining-data-cleaning':
        # 预训练数据清洗的CSV格式 - 纯净语料数据
        return {
            'id': item.get('id', ''),
            'text': item.get('text', ''),
            'source': item.get('source', 'cleaned'),
            'type': item.get('type', 'corpus_text'),
            'length': item.get('length', len(item.get('text', ''))),
            'chunk_index': item.get('chunk_index', 0),
            'segment_index': item.get('segment_index', 0),
            'quality_score': item.get('quality_score', 0.0)
        }
    else:
        return item

def _generate_csv_content(data: List[Dict]) -> str:
    """生成CSV文件内容"""
    import csv
    import io
    
    if not data:
        return ''
    
    # 获取所有字段名
    fieldnames = set()
    for item in data:
        fieldnames.update(item.keys())
    fieldnames = sorted(list(fieldnames))
    
    # 生成CSV内容
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()

def _update_version_stats(version: EnhancedDatasetVersion, conversion_results: List[Dict], 
                         total_generated_entries: int):
    """更新版本统计信息"""
    try:
        # 计算总文件数和大小
        total_files = len([r for r in conversion_results if r.get('status') == 'success'])
        total_size = sum([r.get('file_size', 0) for r in conversion_results if r.get('status') == 'success'])
        
        # 计算成功率
        success_count = len([r for r in conversion_results if r.get('status') == 'success'])
        success_rate = (success_count / len(conversion_results)) * 100 if conversion_results else 0
        
        # 更新版本信息
        version.file_count = total_files
        version.total_size = total_size
        version.data_checksum = hashlib.sha256(
            f"{total_files}{total_size}{total_generated_entries}".encode()
        ).hexdigest()[:16]
        
        # 更新统计信息
        version.stats = {
            'total_generated_entries': total_generated_entries,
            'success_rate': success_rate,
            'processed_files': len(conversion_results),
            'successful_files': success_count,
            'failed_files': len(conversion_results) - success_count,
            'generation_results': conversion_results
        }
        
        version.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"更新版本统计: 文件数={total_files}, 总大小={total_size}, "
                   f"生成条目={total_generated_entries}, 成功率={success_rate:.1f}%")
        
    except Exception as e:
        logger.error(f"更新版本统计失败: {str(e)}")
        # 不抛出异常，避免影响主流程 

def _parse_qa_response_with_thinking(response_data: Dict, dataset_type: str = None, include_thinking: bool = False) -> List[Dict]:
    """解析包含思考过程的问答对响应
    
    Args:
        response_data: 包含raw_response、final_answer、reasoning的字典
        dataset_type: 数据集类型
        include_thinking: 是否在输出中包含思考过程
        
    Returns:
        List[Dict]: 问答对列表
    """
    try:
        # 先从final_answer中解析问答对
        final_answer = response_data.get('final_answer', '')
        reasoning = response_data.get('reasoning', '')
        
        # 使用现有的解析方法解析问答对
        qa_pairs = _parse_qa_response(final_answer, dataset_type)
        
        # 如果需要包含思考过程，为每个问答对添加思考过程
        if include_thinking and reasoning:
            for qa_pair in qa_pairs:
                qa_pair['thinking'] = reasoning
                
        return qa_pairs
        
    except Exception as e:
        logger.error(f"解析包含思考过程的问答对失败: {str(e)}")
        # 如果解析失败，尝试从原始响应解析
        try:
            raw_response = response_data.get('raw_response', '')
            return _parse_qa_response(raw_response, dataset_type)
        except:
            return []

def _parse_summary_response_with_thinking(response_data: Dict, original_text: str, include_thinking: bool = False) -> List[Dict]:
    """解析包含思考过程的摘要响应"""
    try:
        final_answer = response_data.get('final_answer', '')
        reasoning = response_data.get('reasoning', '')
        
        # 使用现有的解析方法解析摘要
        summary_entries = _parse_summary_response(final_answer, original_text)
        
        # 如果需要包含思考过程，为每个摘要添加思考过程
        if include_thinking and reasoning:
            for entry in summary_entries:
                entry['thinking'] = reasoning
                
        return summary_entries
        
    except Exception as e:
        logger.error(f"解析包含思考过程的摘要失败: {str(e)}")
        try:
            raw_response = response_data.get('raw_response', '')
            return _parse_summary_response(raw_response, original_text)
        except:
            return []

def _parse_instruction_response_with_thinking(response_data: Dict, dataset_type: str = None, include_thinking: bool = False) -> List[Dict]:
    """解析包含思考过程的指令响应"""
    try:
        final_answer = response_data.get('final_answer', '')
        reasoning = response_data.get('reasoning', '')
        
        # 使用现有的解析方法解析指令
        instructions = _parse_instruction_response(final_answer, dataset_type)
        
        # 如果需要包含思考过程，为每个指令添加思考过程
        if include_thinking and reasoning:
            for instruction in instructions:
                instruction['thinking'] = reasoning
                
        return instructions
        
    except Exception as e:
        logger.error(f"解析包含思考过程的指令失败: {str(e)}")
        try:
            raw_response = response_data.get('raw_response', '')
            return _parse_instruction_response(raw_response, dataset_type)
        except:
            return []

def _parse_classification_response_with_thinking(response_data: Dict, dataset_type: str = None, include_thinking: bool = False) -> List[Dict]:
    """解析包含思考过程的分类响应"""
    try:
        final_answer = response_data.get('final_answer', '')
        reasoning = response_data.get('reasoning', '')
        
        # 使用现有的解析方法解析分类
        classifications = _parse_classification_response(final_answer, dataset_type)
        
        # 如果需要包含思考过程，为每个分类添加思考过程
        if include_thinking and reasoning:
            for classification in classifications:
                classification['thinking'] = reasoning
                
        return classifications
        
    except Exception as e:
        logger.error(f"解析包含思考过程的分类失败: {str(e)}")
        try:
            raw_response = response_data.get('raw_response', '')
            return _parse_classification_response(raw_response, dataset_type)
        except:
            return [] 

