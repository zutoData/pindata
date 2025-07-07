import numpy as np
import subprocess
import torch
import logging
import colorlog
from dataflow.logger import get_logger
from dataflow.core import get_operator

def pipeline_step(yaml_path, step_name):
    import yaml
    logger = get_logger()
    logger.info(f"Loading yaml {yaml_path} ......")
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    config = merge_yaml(config)
    logger.info(f"Load yaml success, config: {config}")
    algorithm = get_operator(step_name, config)
    logger.info("Start running ...")
    algorithm.run()

def merge_yaml(config):
    if not config.get("vllm_used"):
        return config
    else:
        vllm_args_list = config.get("vllm_args", [])
        if isinstance(vllm_args_list, list) and len(vllm_args_list) > 0 and isinstance(vllm_args_list[0], dict):
            vllm_args = vllm_args_list[0]
            config.update(vllm_args)  # 合并进顶层
        return config
    

def init_model(generator_type:str =None):
    if generator_type is None:
        raise ValueError("generator_type is not found in config")
    if generator_type == "local":
        from dataflow.utils.LocalModelGenerator import LocalModelGenerator
        return LocalModelGenerator(config)
    elif generator_type == "aisuite":
        from dataflow.utils.APIGenerator_aisuite import APIGenerator_aisuite
        return APIGenerator_aisuite(config)
    elif generator_type == "request":
        from dataflow.utils.APIGenerator_request import APIGenerator_request
        return APIGenerator_request(config)
    else:
        raise ValueError(f"Invalid generator type: {config['generator_type']}, must be one of: local, aisuite, request")