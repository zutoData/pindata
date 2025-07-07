from typing import List
import re
from huggingface_hub import hf_hub_download
import fasttext
from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow.utils.storage import DataFlowStorage
from tqdm import tqdm
import numpy as np

@OPERATOR_REGISTRY.register()
class TextbookScorer(OperatorABC):
    def __init__(self, model_cache_dir='./dataflow_cache'):
        self.logger = get_logger()
        self.logger.info(f'Initializing {self.__class__.__name__}...')
        model_path = hf_hub_download(
            repo_id='kenhktsui/llm-data-textbook-quality-fasttext-classifer-v2',
            filename='model.bin',
            cache_dir=model_cache_dir
        )
        low_score=1.0
        mid_score=3.0
        high_score=5.0
        self.model = fasttext.load_model(model_path)
        self.score_type = float
        self.data_type = 'text'
        self.score_name = 'TextbookScore'
        self.score_dict = {
            '__label__Low': low_score,
            '__label__Mid': mid_score,
            '__label__High': high_score
        }
        self.logger.info(f'{self.__class__.__name__} initialized.')

    @staticmethod
    def replace_newlines(text: str) -> str:
        return re.sub("\n+", " ", text)

    def _score_func(self, text_list: List[str]) -> List[float]:
        text_list = [self.replace_newlines(text) for text in text_list]
        pred = self.model.predict(text_list, k=-1)
        
        score_list = []
        for labels, scores in zip(*pred):
            score = 0
            for label, score_value in zip(labels, scores):
                score += self.score_dict.get(label, 0) * score_value
            score_list.append(float(score))
        
        return score_list

    def eval(self, dataframe, input_key):
        scores = []
        text_list = dataframe[input_key]
        self.logger.info(f"Evaluating {self.score_name}...")
        for sample in tqdm(text_list, desc="TextbookScorer Evaluating..."):
            score = self._score_func([sample])
            scores.append(score)
        self.logger.info("Evaluation complete!")
        return np.array(scores)

    def run(self, storage: DataFlowStorage, input_key: str, output_key: str='TextbookScore'):
        dataframe = storage.read("dataframe")  
        scores = self.eval(dataframe, input_key, output_key) 
        for i, score_list in enumerate(scores):
            dataframe[output_key] = score_list 
        storage.write(dataframe) 
