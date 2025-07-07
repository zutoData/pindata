from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow.operators.eval.GeneralText import TextbookScorer

@OPERATOR_REGISTRY.register()
class TextbookFilter(OperatorABC):

    def __init__(self, min_score=0.99, max_score=1, model_cache_dir:str='./dataflow_cache'):
        self.logger = get_logger()
        self.min_score = min_score
        self.max_score = max_score
        self.scorer = TextbookScorer(model_cache_dir=model_cache_dir)
        self.logger.info(f"Initializing {self.__class__.__name__} with min_score = {min_score} and max_score = {max_score}")

    def run(self, storage: DataFlowStorage, input_key: str, output_key: str='TextbookScore'):
        self.input_key = input_key
        self.output_key = output_key
        dataframe = storage.read("dataframe")
        scores = self.scorer.eval(dataframe, self.input_key)
        dataframe[self.output_key] = scores
        filtered_dataframe = dataframe[(dataframe[self.output_key] >= self.min_score) & (dataframe[self.output_key] <= self.max_score)]
        output_file = storage.write(filtered_dataframe)
        self.logger.info(f"Filtering completed. Total records passing filter: {len(filtered_dataframe)}.")
        return [self.output_key]
        
        