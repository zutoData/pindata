#!/usr/bin/env python3
"""
task_definitions.py  ── Task factory registrations for agent workflow pipeline
Author  : [Zhou Liu]
License : MIT
Created : 2024-07-02

This module defines and registers a collection of Task factory functions using TaskRegistry.
Each factory specifies configuration, templates, and parameter functions for a specific agent task.

Features:
* Centralized registration of all supported task types (conversation, classification, pipeline inference, pipeline execution, etc.)
* Easy extension: add new task factories with the @TaskRegistry.register decorator.
* Parameter functions are injected for dynamic, context-aware task execution.
* Maintains a unified configuration resource directory for task YAML files.

Intended for use in agent workflow orchestration, enabling modular and dynamic task dispatch.

Thread-safety: Task registration is not thread-safe by default; use with care in concurrent environments.
"""
import os
from .task_dispatcher import Task
from ..toolkits import combine_pipeline_result,local_tool_for_get_purpose,local_tool_for_sample,get_operator_content,local_tool_for_get_chat_target,get_operator_content_map_from_all_operators,local_tool_for_get_chat_history,local_tool_for_execute_the_recommended_pipeline,local_tool_for_get_categories
from .task_reg import TaskRegistry
from dataflow.cli_funcs.paths import DataFlowPath

yaml_dir = f"{DataFlowPath.get_dataflow_agent_dir()}/taskcenter/resources"

@TaskRegistry.register('conversation_router')
def _make_conversation_router(prompts_template,request):
    return Task(
        request=request,
        config_path=f'{yaml_dir}/TaskInfo.yaml',
        prompts_template=prompts_template,
        system_template="system_prompt_for_chat",
        task_template="task_prompt_for_chat",
        param_funcs={
            "history": local_tool_for_get_chat_history,
            "target": local_tool_for_get_chat_target
        },
        is_result_process=False,
        use_pre_task_result = False,
        task_name= "conversation_router"
    )

@TaskRegistry.register('data_content_classification')
def _make_data_content_classification(prompts_template,request):
    return Task(
        request=request,
        config_path=f'{yaml_dir}/TaskInfo.yaml',
        prompts_template=prompts_template,
        system_template="system_prompt_for_data_content_classification",
        task_template="task_prompt_for_data_content_classification",
        param_funcs={
            "local_tool_for_sample": local_tool_for_sample,
            "local_tool_for_get_categories": local_tool_for_get_categories
        },
        is_result_process=False,
        use_pre_task_result = False,
        task_name= "data_content_classification"
    )
@TaskRegistry.register('recommendation_inference_pipeline')
def _make_recommendation_task(prompts_template,request):
    return  Task(
        request=request,
        config_path=f'{yaml_dir}/TaskInfo.yaml',
        prompts_template=prompts_template,
        system_template="system_prompt_for_recommendation_inference_pipeline",
        task_template="task_prompt_for_recommendation_inference_pipeline",
        param_funcs={
            "local_tool_for_sample": local_tool_for_sample,
            # "operator": get_operator_content,
            "operator": get_operator_content_map_from_all_operators,
            "workflow_bg":local_tool_for_get_purpose

        },
        is_result_process=True,
        task_result_processor = combine_pipeline_result,
        use_pre_task_result = True,
        task_name="recommendation_inference_pipeline"
    )
@TaskRegistry.register('execute_the_recommended_pipeline')
def _make_execute_the_recommended_pipeline(prompts_template,request):
    return  Task(
        request=request,
        config_path=f'{yaml_dir}/TaskInfo.yaml',
        prompts_template=prompts_template,
        system_template="system_prompt_for_execute_the_recommended_pipeline",
        task_template="task_prompt_for_execute_the_recommended_pipeline",
        param_funcs={
            "local_tool_for_execute_the_recommended_pipeline":local_tool_for_execute_the_recommended_pipeline
        },
        is_result_process=False,
        use_pre_task_result=True,
        task_name="execute_the_recommended_pipeline"
    )

# @TaskRegistry.register('operator_auto_update')
# def _make_operator_auto_update(prompts_template):
#     """
#     算子自动更新任务生成器。
#     你可以在 param_funcs 中添加各个算子的更新函数，
#     比如 {"update_op1": func1, "update_op2": func2, …}
#     """
#     return Task(
#         config_path=f'{yaml_dir}/TaskInfo.yaml',
#         prompts_template=prompts_template,
#         system_template="system_prompt_for_operator_auto_update",
#         task_template="task_prompt_for_operator_auto_update",
#         param_funcs={
#             # TODO: 在这里填入算子更新所需的参数函数映射
#             # 如 "refresh_operator_list": refresh_op_list_func,
#             #    "generate_update_payload": make_payload_func
#         }
#     )