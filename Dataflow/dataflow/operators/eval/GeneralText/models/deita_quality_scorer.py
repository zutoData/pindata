from dataflow.core import OperatorABC
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow.utils.storage import DataFlowStorage
from transformers import AutoTokenizer, AutoModelForCausalLM
import numpy as np
from scipy.special import softmax
import requests
import torch
from dataflow import get_logger
from tqdm import tqdm

@OPERATOR_REGISTRY.register()
class DeitaQualityScorer(OperatorABC):
    def __init__(self, device='cuda', model_cache_dir='./dataflow_cache', max_length=512):
        self.logger = get_logger()
        self.logger.info(f'Initializing {self.__class__.__name__}...')
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_name = 'hkust-nlp/deita-quality-scorer'
        self.model_cache_dir = model_cache_dir
        self.max_length = max_length
        self.token_strs = ["1", "2", "3", "4", "5", "6"]
        self.score_template = np.array([1, 2, 3, 4, 5, 6])
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=self.model_cache_dir)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name, cache_dir=self.model_cache_dir).to(self.device)
        self.score_name = 'DeitaQualityScore'
        self.logger.info(f'{self.__class__.__name__} initialized.')

    @staticmethod
    def get_desc(lang: str = "zh"):
        return "使用Deita指令质量分类器评估指令质量" if lang == "zh" else "Evaluate instruction quality using the Deita instruction quality classifier."

    def infer_quality(self, input_text, resp_text):
        # Define the template and input format
        quality_template = ("You are a helpful assistant. Please identify the quality score of the Response corresponding to the Question.\n"
                            "#Question#:\n{instruction}\n#Response#:\n{output}\n##Quality: ")
        user_input = quality_template.format(instruction=input_text, output=resp_text)

        
        input_ids = self.tokenizer.encode(user_input, return_tensors="pt").to(self.device)
        outputs = self.model.generate(input_ids, max_new_tokens=self.max_length, num_return_sequences=1, return_dict_in_generate=True, output_scores=True)
        logprobs_list = outputs.scores[0][0]

        id2score = {
            29896: "1",
            29906: "2",
            29941: "3",
            29946: "4",
            29945: "5",
            29953: "6"
        }

        score_logits = []
        for k in id2score:
            score_logits.append(logprobs_list[k].cpu().numpy())

        score_logits = np.array(score_logits)
        score_npy = softmax(score_logits, axis=0)
        score_npy = score_npy * self.score_template
        final_score = np.sum(score_npy, axis=0)
        return final_score

    def eval(self, dataframe, input_instruction_key: str = 'instruction', input_output_key: str = 'output'):
        scores = []
        self.logger.info(f"Evaluating {self.score_name}...")
        for sample in tqdm(dataframe[[input_instruction_key, input_output_key]].to_dict(orient='records'), desc="Deita quality model Evaluating..."):
            quality_score = self.infer_quality(sample[input_instruction_key], sample[input_output_key])  # assuming response and instruction are the same for now
            scores.append(quality_score)
        self.logger.info("Evaluation complete!")
        return scores

    def run(self, storage: DataFlowStorage, input_instruction_key: str = 'instruction', input_output_key: str = 'output', output_key: str = 'DeitaQualityScore'):
        dataframe = storage.read("dataframe")
        scores = self.eval(dataframe, input_instruction_key, input_output_key)
        dataframe[output_key] = scores        
        storage.write(dataframe)
