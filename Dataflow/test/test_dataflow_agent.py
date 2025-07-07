import os, asyncio
from fastapi import FastAPI
from pathlib import Path
from dataflow.agent.promptstemplates.prompt_template import PromptsTemplateGenerator
from dataflow.agent.taskcenter import TaskRegistry
import dataflow.agent.taskcenter.task_definitions
from dataflow.agent.servicemanager import AnalysisService, Memory
from dataflow.agent.toolkits import (
    ChatResponse,
    ChatAgentRequest,
    ToolRegistry,
)
from dataflow.agent.agentrole.debugger import DebugAgent
from dataflow.agent.agentrole.executioner import ExecutionAgent
from dataflow.cli_funcs.paths import DataFlowPath
from dataflow import get_logger
logger = get_logger()     
toolkit = ToolRegistry()
memorys = {
    "planner": Memory(),
    "analyst": Memory(),
    "executioner": Memory(),
    "debugger": Memory(),
}
BASE_DIR = DataFlowPath.get_dataflow_dir()
DATAFLOW_DIR = BASE_DIR.parent

def _build_task_chain(req: ChatAgentRequest, tmpl:PromptsTemplateGenerator):
    router   = TaskRegistry.get("conversation_router", prompts_template=tmpl,request=req)
    classify = TaskRegistry.get("data_content_classification", prompts_template=tmpl,request=req)
    rec      = TaskRegistry.get("recommendation_inference_pipeline", prompts_template=tmpl,request=req)
    exe      = TaskRegistry.get("execute_the_recommended_pipeline", prompts_template=tmpl,request=req)
    return [router, classify, rec, exe]


async def _run_service(req: ChatAgentRequest) -> ChatResponse:
    tmpl = PromptsTemplateGenerator(req.language)
    task_chain = _build_task_chain(req,tmpl = tmpl)
    execution_agent = ExecutionAgent(
                              req,
                              memorys["executioner"],
                              tmpl,
                              debug_agent=DebugAgent(task_chain[-1],memorys["debugger"],req),
                              task_chain= task_chain
                              )
    
    service = AnalysisService(
        tasks= task_chain,
        memory_entity=memorys["analyst"],
        request=req,
        execution_agent= execution_agent
    )
    return await service.process_request()

app = FastAPI(title="Dataflow Agent Service")
@app.post("/recommend", response_model=ChatResponse)
async def recommend(req: ChatAgentRequest):
    return await _run_service(req)

@app.post("/recommend_and_execute", response_model=ChatResponse)
async def recommend_and_execute(req: ChatAgentRequest):
    return await _run_service(req)

if __name__ == "__main__":
    import uvicorn, json, sys
    if len(sys.argv) == 2 and sys.argv[1] == "request":
        test_req = ChatAgentRequest(
            language="zh", #en 或者 zh
            target="帮我针对数据推荐一个预测的 pipeline!!!我只想要前4个处理算子！！！其余的都不要！！",
            # target="你好！今天武汉天气如何？？",
            api_key =  "",
            chat_api_url = "",
            model="deepseek-v3",
            sessionKEY="dataflow_demo",
            json_file = f"{DATAFLOW_DIR}/dataflow/example/ReasoningPipeline/pipeline_math_short.json",
            py_path = f"{DATAFLOW_DIR}/test/recommend_pipeline_2.py",
            execute_the_pipeline =  True,
            use_local_model = True,
            local_model_name_or_path = "/mnt/public/model/huggingface/Qwen2.5-7B-Instruct",
            timeout = 3600,
            max_debug_round = 5
        )
        resp = asyncio.run(_run_service(test_req))
        print(json.dumps(resp.dict(), ensure_ascii=False, indent=2))
    else:
        uvicorn.run("test_dataflow_agent:app", host="0.0.0.0", port=8000, reload=True)