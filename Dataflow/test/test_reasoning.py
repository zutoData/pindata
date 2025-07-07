import pytest
from dataflow.operators.generate.Reasoning import (
    QuestionCategoryClassifier,
    QuestionDifficultyClassifier,
    QuestionGenerator,
    AnswerGenerator,
)

from dataflow.operators.process.Reasoning import *
from dataflow.utils.storage import FileStorage
from dataflow.serving import APILLMServing_request, LocalModelLLMServing
from dataflow.core import LLMServingABC

# 这里或许未来可以有个pipeline基类
class ReasoningPipeline():
    def __init__(self, llm_serving: LLMServingABC = None):

        self.storage = FileStorage(
            first_entry_file_name="../dataflow/example/ReasoningPipeline/pipeline_math_short.json",
            cache_path="./cache_local",
            file_name_prefix="dataflow_cache_step",
            cache_type="jsonl",
        )

        # use API server as LLM serving
        # llm_serving = APILLMServing_request(
        #         api_url="http://123.129.219.111:3000/v1/chat/completions",
        #         model_name="gpt-4o",
        #         max_workers=100
        # )
        if llm_serving is None:
            # use local model as LLM serving
            llm_serving = LocalModelLLMServing(
                # model_name_or_path="/data0/models/Qwen2.5-7B-Instruct", # set to your own model path
                model_name_or_path="/mnt/public/model/huggingface/Qwen2.5-7B-Instruct",
                tensor_parallel_size=4,
                max_tokens=8192,
                model_source="local"
            )

        self.question_filter_step1 = QuestionFilter(
            system_prompt="You are an expert in evaluating mathematical problems. Follow the user's instructions strictly and output your final judgment in the required JSON format.",
            llm_serving=llm_serving
        )
        self.question_gen_step2 =  QuestionGenerator(
            num_prompts=3,
            llm_serving=llm_serving
        )
        self.question_filter_step3 = QuestionFilter(
            system_prompt="You are an expert in evaluating mathematical problems. Follow the user's instructions strictly and output your final judgment in the required JSON format.",
            llm_serving=llm_serving
        )
        self.question_difficulty_classifier_step4 = QuestionDifficultyClassifier(
            llm_serving=llm_serving
        )
        self.question_category_classifier_step5 = QuestionCategoryClassifier(
            llm_serving=llm_serving
        )
        ########################## branch ############################
        self.answer_pipeline_root_step6 = AnswerPipelineRoot()
        ########################## answer ############################
        self.answer_generator_step7 = AnswerGenerator(
            llm_serving=llm_serving
        )
        
        self.answer_format_filter_step8 = AnswerFormatterFilter()
        
        self.answer_token_length_filter_step9 = AnswerTokenLengthFilter(
            max_answer_token_length = 8192,
            tokenizer_dir = "Qwen/Qwen2.5-0.5B-Instruct"
        )
        
        self.answer_groundtruth_filter_step10 = AnswerGroundTruthFilter()
        
        self.answer_ngram_filter_step11 = AnswerNgramFilter(
            min_score = 0.1,
            max_score = 1.0,
            ngrams = 5
        )
        
        # 未来或许可以维护一个类似nn.sequential的容器，方便添加并实例化多个算子
    def forward(self):

        self.question_filter_step1.run(
            storage = self.storage.step(),
            input_key = "instruction",
        )

        self.question_gen_step2.run(
            storage = self.storage.step(),
            input_key = "instruction",
        )

        self.question_filter_step3.run(
            storage = self.storage.step(),
            input_key = "instruction",
        )

        self.question_difficulty_classifier_step4.run(
            storage = self.storage.step(),
            input_key = "instruction",
            output_key = "question_difficulty"
        )

        self.question_category_classifier_step5.run(
            storage = self.storage.step(),
            input_key = "instruction",
            output_key = "question_category"
        )
        ############# branch #############
        self.answer_pipeline_root_step6.run(
            storage = self.storage.step(),
            input_answer_key = "output",
            input_gt_key = "golden_answer"
        )
        ############## answer #############
        self.answer_generator_step7.run(
            storage = self.storage.step(),
            input_key = "instruction", 
            output_key = "generated_cot"
        )
        self.answer_format_filter_step8.run(
            storage = self.storage.step(),
            input_key = "generated_cot",
        )
        self.answer_token_length_filter_step9.run(
            storage = self.storage.step(),
            input_key =  "generated_cot"
        )
        self.answer_groundtruth_filter_step10.run(
            storage = self.storage.step(),
            test_answer_key = "generated_cot",
            gt_answer_key =  "golden_answer"
        )
        self.answer_ngram_filter_step11.run(
            storage = self.storage.step(),
            question_key = "instruction",
            answer_key = "generated_cot"
        )
        
# @pytest.mark.gpu
# def test_reasoning_pipeline_runs_without_errors():
#     try:
#         pipeline = ReasoningPipeline()
#         pipeline.forward()
#     except Exception as e:
#         pytest.fail(f"ReasoningPipeline execution failed with error: {e}")
if __name__ == "__main__":
    model = ReasoningPipeline()
    model.forward()
