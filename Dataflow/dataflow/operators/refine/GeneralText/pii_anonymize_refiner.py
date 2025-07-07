from tqdm import tqdm
from transformers import AutoModelForTokenClassification, AutoTokenizer
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY

@OPERATOR_REGISTRY.register()
class PIIAnonymizeRefiner(OperatorABC):
    def __init__(self, lang='en', device='cuda', model_cache_dir='./dataflow_cache', model_name='dslim/bert-base-NER', ):
        self.logger = get_logger()
        self.logger.info(f"Initializing {self.__class__.__name__} ...")
        self.lang = lang
        self.device = device
        self.model_cache_dir = model_cache_dir
        self.model_name = model_name
        model_name = 'dslim/bert-base-NER'
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=self.model_cache_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(model_name, cache_dir=self.model_cache_dir).to(self.device)
        model_config = [{
            "lang_code": self.lang,
            "model_name": {
                "spacy": "en_core_web_sm",
                "transformers": model_name
            }
        }]
        
        self.nlp_engine = TransformersNlpEngine(models=model_config)
        self.analyzer = AnalyzerEngine(nlp_engine=self.nlp_engine)
        self.anonymizer = AnonymizerEngine()

    @staticmethod
    def get_desc(lang: str = "zh"):
        return "去除文本中的URL和HTML标签" if lang == "zh" else "Remove URLs and HTML tags from the text."

    def run(self, storage: DataFlowStorage, input_key: str):
        self.input_key = input_key
        dataframe = storage.read("dataframe")
        self.logger.info(f"Running {self.__class__.__name__} with input_key = {self.input_key}...")
        anonymized_count = 0
        refined_data = []
        for item in tqdm(dataframe[self.input_key], desc=f"Implementing {self.__class__.__name__}"):
            modified = False  
            original_text = item
            results = self.analyzer.analyze(original_text, language=self.lang)
            anonymized_text = self.anonymizer.anonymize(original_text, results)
            if original_text != anonymized_text.text:
                item = anonymized_text.text
                modified = True
            self.logger.debug(f"Modified text for key '{self.input_key}': Original: {original_text[:30]}... -> Refined: {anonymized_text.text[:30]}...")

            refined_data.append(item)
            if modified:
                anonymized_count += 1
                self.logger.debug(f"Item modified, total modified so far: {anonymized_count}")
        self.logger.info(f"Refining Complete. Total modified items: {anonymized_count}")
        dataframe[self.input_key] = refined_data
        output_file = storage.write(dataframe)
        return [self.input_key]