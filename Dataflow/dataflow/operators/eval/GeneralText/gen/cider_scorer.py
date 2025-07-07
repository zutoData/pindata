import os
import json
import pickle
from tqdm import tqdm
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow import get_logger
from dataflow.operators.eval.GeneralText.gen.cider.cider import Cider

def load_idf(idf_path):
    with open(idf_path, 'rb') as f:
        idf = pickle.load(f, encoding='utf-8')  
    return idf

@OPERATOR_REGISTRY.register()
class CiderScorer(OperatorABC):
    def __init__(self, n=4, sigma=6.0, df_mode="coco-val-df", idf_path="./dataflow/operators/eval/GeneralText/gen/cider/coco-val-df.p"):
        self.logger = get_logger()
        self.logger.info(f'Initializing {self.__class__.__name__}...')
        self.score_name = 'CiderScore'
        self.n = n  # Max n-gram length (default: 4)
        self.sigma = sigma  # Sigma for Gaussian penalty (default: 6.0)
        self.df_mode = df_mode
        if self.df_mode != "corpus":
            # The idf file can be downloaded at https://github.com/ramavedantam/coco-caption/blob/master/data/coco-val-df.p
            # Put the file in the correct idf_path
            self.idf = load_idf(idf_path)
        else:
            self.idf = None  # No need to load IDF for 'corpus' mode
        self.logger.info(f'{self.__class__.__name__} initialized.')
    
    def _score_func(self, eval_text, ref_text):
        cider_scorer = Cider(
            test=eval_text,
            refs=[ref_text],
            n=self.n,
            sigma=self.sigma,
            idf=self.idf  # Pass IDF (None if using 'corpus')
        )
        # Pass df_mode dynamically based on the argument
        cider_score, _ = cider_scorer.compute_score(df_mode='corpus' if self.idf is None else 'coco-val-df')  
        return cider_score

    def eval(self, dataframe, input_key, reference_key):
        eval_data = dataframe[input_key]
        ref_data = dataframe[reference_key]
        self.logger.info(f"Evaluating {self.score_name}...")
        scores = [self._score_func(eval_text, ref_text) for eval_text, ref_text in tqdm(zip(eval_data, ref_data), desc="CiderScorer Evaluating...")]
        self.logger.info("Evaluation complete!")
        return scores
    
    def run(self, storage: DataFlowStorage, input_key: str, reference_key: str, output_key: str='CiderScore'):
        self.input_key = input_key
        self.reference_key = reference_key
        self.output_key = output_key
        dataframe = storage.read("dataframe")
        scores = self.eval(dataframe, input_key, reference_key)
        dataframe[self.output_key] = scores
        storage.write(dataframe)
