import os
import tempfile
import logging
from datetime import datetime
from celery import Task, group, chord
from flask import current_app
from app.celery_app import celery
from app.models import (
    ConversionJob, ConversionStatus, ConversionFileDetail,
    LibraryFile, ProcessStatus, Task as TaskModel, TaskStatus,
    LLMConfig
)
from app.services.storage_service import storage_service
from app.services.llm_conversion_service import llm_conversion_service
from app.db import db
import markitdown
import time

logger = logging.getLogger(__name__)

class ConversionTask(Task):
    """自定义任务类，用于处理应用上下文"""
    _flask_app = None
    _markitdown = None

    @property
    def flask_app(self):
        if self._flask_app is None:
            # 延迟导入，避免循环依赖
            from app import create_app
            self._flask_app = create_app()
        return self._flask_app
    
    @property
    def markitdown(self):
        if self._markitdown is None:
            self._markitdown = markitdown.MarkItDown()
        return self._markitdown

@celery.task(base=ConversionTask, bind=True, name='tasks.process_conversion_job')
def process_conversion_job(self, job_id: str):
    """
    调度转换任务。
    这个任务会为每个文件分发一个独立的 `convert_one_file_task` 子任务。
    """
    with self.flask_app.app_context():
        logger.info(f"开始调度转换任务: {job_id}")
        job = ConversionJob.query.get(job_id)
        if not job:
            logger.error(f"调度失败：转换任务不存在: {job_id}")
            return {'success': False, 'error': '任务不存在'}

        # 检查是否有文件需要处理
        if not job.file_details or len(job.file_details) == 0:
            logger.warning(f"任务 {job_id} 中没有需要转换的文件，直接标记为完成。")
            job.status = ConversionStatus.COMPLETED
            job.task.status = TaskStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.task.completed_at = datetime.utcnow()
            db.session.commit()
            return {'success': True, 'message': '没有文件需要转换'}

        # 更新主任务状态
        job.status = ConversionStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.task.status = TaskStatus.RUNNING
        job.task.started_at = datetime.utcnow()
        job.add_log(f"开始调度 {len(job.file_details)} 个文件的转换子任务...")
        db.session.commit()

        # 为每个文件创建一个子任务组
        task_group = group(
            convert_one_file_task.s(file_detail.id)
            for file_detail in job.file_details
        )

        # 使用 chord，在所有子任务完成后调用 finalize_conversion_job 进行汇总
        callback_task = finalize_conversion_job.s(job_id)
        chord(task_group)(callback_task)

        logger.info(f"已为任务 {job_id} 创建 {len(job.file_details)} 个转换子任务。")
        return {'success': True, 'job_id': job_id, 'dispatched_tasks': len(job.file_details)}


@celery.task(base=ConversionTask, bind=True, name='tasks.convert_one_file')
def convert_one_file_task(self, file_detail_id: str):
    """转换单个文件的 Celery 任务"""
    with self.flask_app.app_context():
        start_time = time.time()
        
        # 使用with_for_update来锁定行，避免并发问题
        file_detail = db.session.query(ConversionFileDetail).filter_by(id=file_detail_id).with_for_update().first()
        
        if not file_detail:
            logger.error(f"文件详情记录不存在: {file_detail_id}")
            return {'success': False, 'file_detail_id': file_detail_id, 'error': 'File detail not found'}

        # 如果文件已经被处理，则跳过
        if file_detail.status not in [ConversionStatus.PENDING, ConversionStatus.FAILED]:
            logger.warning(f"文件 {file_detail.library_file.original_filename} 状态为 {file_detail.status}，跳过处理。")
            return {'success': True, 'file_detail_id': file_detail_id, 'skipped': True}
            
        job = file_detail.conversion_job
        file_name = file_detail.library_file.original_filename if file_detail.library_file else 'unknown'

        try:
            # 标记文件开始处理
            file_detail.status = ConversionStatus.PROCESSING
            file_detail.started_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"开始处理文件: {file_name} (Job: {job.id})")
            _convert_single_file_logic(self, file_detail)

            duration = time.time() - start_time
            logger.info(f"文件处理成功: {file_name}, 耗时: {duration:.2f}s")
            return {'success': True, 'file_detail_id': file_detail_id}

        except Exception as e:
            db.session.rollback()
            # 在异常中重新获取会话和对象
            file_detail = db.session.query(ConversionFileDetail).get(file_detail_id)
            file_name = file_detail.library_file.original_filename if file_detail.library_file else 'unknown'

            duration = time.time() - start_time
            logger.error(f"转换文件失败: {file_name}, 耗时: {duration:.2f}s, 错误: {str(e)}", exc_info=True)
            
            file_detail.status = ConversionStatus.FAILED
            file_detail.error_message = str(e)
            db.session.commit()
            
            # 返回失败结果，但不抛出异常，以确保 chord 的 callback 能被调用
            return {'success': False, 'file_detail_id': file_detail_id, 'error': str(e)}


@celery.task(base=ConversionTask, bind=True, name='tasks.finalize_conversion_job')
def finalize_conversion_job(self, results, job_id: str):
    """所有文件转换子任务完成后，调用此任务进行汇总。"""
    with self.flask_app.app_context():
        logger.info(f"开始汇总转换任务: {job_id}")
        job = ConversionJob.query.get(job_id)
        if not job:
            logger.error(f"汇总失败：转换任务不存在: {job_id}")
            return

        db.session.refresh(job)
        if job.status == ConversionStatus.CANCELLED:
            logger.info(f"任务 {job_id} 已被取消，无需汇总。")
            return

        # 根据子任务的返回结果统计成功和失败的数量
        completed_count = sum(1 for r in results if r.get('success') or r.get('skipped'))
        failed_count = len(results) - completed_count

        job.completed_count = completed_count
        job.failed_count = failed_count
        job.update_progress()
        job.task.progress = int(job.progress_percentage)

        total_duration = (datetime.utcnow() - job.started_at).total_seconds()

        if failed_count == 0:
            job.status = ConversionStatus.COMPLETED
            job.task.status = TaskStatus.COMPLETED
            message = f'所有 {completed_count} 个文件转换成功'
        else:
            job.status = ConversionStatus.COMPLETED
            job.task.status = TaskStatus.COMPLETED
            job.error_message = f"{failed_count} 个文件转换失败"
            message = f"转换完成: 成功 {completed_count} 个, 失败 {failed_count} 个"

        job.completed_at = datetime.utcnow()
        job.task.completed_at = datetime.utcnow()
        
        job.add_log(f"任务汇总完成: {message}, 总耗时: {total_duration:.1f}秒")
        db.session.commit()
        logger.info(f"转换任务 {job_id} 已汇总完成. {message}")


def _convert_single_file_logic(celery_task, file_detail: ConversionFileDetail):
    """
    转换单个文件的核心逻辑（无状态更新，只做转换和I/O）。
    被 `convert_one_file_task` 调用。
    """
    job = file_detail.conversion_job
    library_file = file_detail.library_file

    # 检查任务是否在开始时就被取消
    db.session.refresh(job)
    if job.status == ConversionStatus.CANCELLED:
        file_detail.status = ConversionStatus.CANCELLED
        db.session.commit()
        logger.info(f"文件转换被取消: {library_file.original_filename}")
        raise Exception("Job was cancelled before processing")

    with tempfile.NamedTemporaryFile(suffix=f".{library_file.file_type}", delete=False) as tmp_file:
        try:
            storage_service.download_file(
                current_app.config.get('MINIO_RAW_DATA_BUCKET', 'raw-data'),
                library_file.minio_object_name,
                tmp_file.name
            )
            
            db.session.refresh(job)
            if job.status == ConversionStatus.CANCELLED:
                raise Exception("Job was cancelled after download")

            if job.method == 'markitdown':
                markdown_content = _convert_with_markitdown(
                    celery_task, tmp_file.name, library_file.file_type, job.conversion_config
                )
            else:
                markdown_content = _convert_with_llm(
                    tmp_file.name, library_file.file_type, job.conversion_config, job.llm_config_id, file_detail
                )
            
            db.session.refresh(job)
            if job.status == ConversionStatus.CANCELLED:
                raise Exception("Job was cancelled after conversion")

            markdown_filename = f"{os.path.splitext(library_file.original_filename)[0]}.md"
            markdown_object_name = f"converted/{library_file.library_id}/{library_file.id}/{markdown_filename}"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8', delete=False) as md_file:
                try:
                    md_file.write(markdown_content)
                    md_file.flush()
                    storage_service.upload_file_from_path(
                        md_file.name,
                        markdown_object_name,
                        content_type='text/markdown; charset=utf-8',
                        bucket_name=current_app.config.get('MINIO_DATASETS_BUCKET', 'datasets')
                    )
                    file_size = os.path.getsize(md_file.name)
                finally:
                    os.unlink(md_file.name)

            # 更新数据库记录
            file_detail.status = ConversionStatus.COMPLETED
            file_detail.completed_at = datetime.utcnow()
            file_detail.converted_object_name = markdown_object_name
            file_detail.converted_file_size = file_size
            
            library_file.process_status = ProcessStatus.COMPLETED
            library_file.converted_format = 'markdown'
            library_file.converted_object_name = markdown_object_name
            library_file.converted_file_size = file_size
            library_file.conversion_method = job.method
            library_file.processed_at = datetime.utcnow()
            db.session.commit()

        finally:
            os.unlink(tmp_file.name)

def _convert_with_markitdown(celery_task, file_path: str, file_type: str, config: dict) -> str:
    """使用markitdown转换文档"""
    try:
        result = celery_task.markitdown.convert(file_path)
        return result.text_content
    except Exception as e:
        logger.error(f"Markitdown转换失败: {str(e)}")
        raise

def _convert_with_llm(file_path: str, file_type: str, config: dict, llm_config_id: str, file_detail: ConversionFileDetail) -> str:
    """使用LLM转换文档"""
    try:
        # 获取LLM配置
        llm_config = LLMConfig.query.get(llm_config_id)
        if not llm_config:
            raise ValueError(f"LLM配置不存在: {llm_config_id}")
        
        # 添加调试信息
        logger.info(f"转换任务中获取到的LLM配置: ID={llm_config.id}, Name={llm_config.name}, Provider={llm_config.provider}")
        logger.info(f"API Key前缀: {llm_config.api_key[:10]}... (长度: {len(llm_config.api_key)})")
        
        # 强制清除LLM客户端缓存，确保使用最新配置
        if hasattr(llm_conversion_service, 'llm_cache') and llm_config.id in llm_conversion_service.llm_cache:
            logger.info(f"清除LLM客户端缓存: {llm_config.id}")
            del llm_conversion_service.llm_cache[llm_config.id]
        
        # 记录文件转换开始
        file_name = os.path.basename(file_path)
        logger.info(f"开始LLM转换 - 文件: {file_name}, 类型: {file_type}")
        logger.info(f"转换配置: enableOCR={config.get('enableOCR', True)}, extractImages={config.get('extractImages', False)}")
        
        # 定义增强的进度回调函数
        def progress_callback(current_page: int, total_pages: int):
            try:
                # 更新文件级别的进度
                file_detail.processed_pages = current_page
                file_detail.total_pages = total_pages
                
                # 计算文件内部进度百分比
                if total_pages > 0:
                    file_progress = (current_page / total_pages) * 100
                    logger.info(f"文件内部进度 - {file_name}: {current_page}/{total_pages} 页 ({file_progress:.1f}%)")
                    
                    # 添加页面进度日志到数据库
                    if hasattr(progress_callback, '_job_ref'):
                        job = progress_callback._job_ref
                        job.add_log(f"页面进度 - {file_name}: {current_page}/{total_pages} 页 ({file_progress:.1f}%)")
                else:
                    file_progress = 0
                
                # 更新数据库
                db.session.commit()
                
                # 记录进度更新
                logger.debug(f"进度回调更新成功 - 文件: {file_name}, 当前页: {current_page}, 总页数: {total_pages}")
                
            except Exception as e:
                logger.warning(f"进度回调失败 - 文件: {file_name}, 错误: {str(e)}")
        
        # 将job引用传递给回调函数（通过属性）
        progress_callback._job_ref = ConversionJob.query.get(file_detail.conversion_job_id)
        
        # 调用LLM转换服务
        start_time = time.time()
        markdown_content = llm_conversion_service.convert_document_with_vision(
            file_path=file_path,
            file_type=file_type,
            llm_config=llm_config,
            conversion_config=config,
            progress_callback=progress_callback
        )
        conversion_duration = time.time() - start_time
        
        # 记录转换完成信息
        logger.info(f"LLM转换完成 - 文件: {file_name}, 耗时: {conversion_duration:.2f}秒, 输出长度: {len(markdown_content)} 字符")
        
        # 更新LLM使用统计
        llm_config.update_usage()
        
        return markdown_content
        
    except Exception as e:
        logger.error(f"LLM转换失败 - 文件: {file_name if 'file_name' in locals() else 'unknown'}: {str(e)}")
        # 记录详细错误信息用于调试
        if 'llm_config' in locals():
            logger.error(f"LLM配置详情: Provider={llm_config.provider}, Model={llm_config.model_name}")
        raise 