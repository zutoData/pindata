from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow import get_logger
from dataflow.operators.eval.GeneralText.gen.bleu.bleu import Bleu
from tqdm import tqdm

@OPERATOR_REGISTRY.register()
class BleuScorer(OperatorABC):
    def __init__(self, n=4, eff="average", special_reflen=None):
        self.logger = get_logger()
        self.logger.info(f'Initializing {self.__class__.__name__}...')
        self.score_name = 'BleuScore'
        valid_eff_options = ["shortest", "average", "longest"]
        if eff not in valid_eff_options:
            raise ValueError(f"Invalid value for 'eff'. Must be one of {valid_eff_options}, but got '{eff}'.")
        self.n = n  # Max n-gram length (default: 4)
        self.eff = eff  # [shortest, average, longest]
        self.special_reflen = special_reflen  # Special reference length if specified
        self.logger.info(f'{self.__class__.__name__} initialized.')
    
    def _score_func(self, eval_text, ref_text):
        bleu_scorer = Bleu(
            test=eval_text,
            refs=[ref_text],
            n=self.n,
            special_reflen=self.special_reflen,
        )
        bleu_score, _ = bleu_scorer.compute_score(option=self.eff)
        return bleu_score[0]
    
    def eval(self, dataframe, input_key, reference_key):
        eval_data = dataframe[input_key]
        ref_data = dataframe[reference_key]
        self.logger.info(f"Evaluating {self.score_name}...")
        scores = [self._score_func(eval_text, ref_text) for eval_text, ref_text in tqdm(zip(eval_data, ref_data), desc="BleuScorer Evaluating...")]
        self.logger.info("Evaluation complete!")
        return scores
    
    def run(self, storage: DataFlowStorage, input_key: str, reference_key: str, output_key: str='BleuScore'):
        self.input_key = input_key
        self.reference_key = reference_key
        self.output_key = output_key
        dataframe = storage.read("dataframe")        
        scores = self.eval(dataframe, input_key, reference_key)
        dataframe[self.output_key] = scores
        storage.write(dataframe)
