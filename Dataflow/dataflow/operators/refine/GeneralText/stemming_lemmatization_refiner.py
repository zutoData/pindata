import nltk
from nltk.stem import PorterStemmer, WordNetLemmatizer
from tqdm import tqdm
from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY

@OPERATOR_REGISTRY.register()
class StemmingLemmatizationRefiner(OperatorABC):
    def __init__(self, method: str = "stemming"):
        self.logger = get_logger()
        self.logger.info(f"Initializing {self.__class__.__name__} ...")
        self.method = method.lower()
        if self.method not in ["stemming", "lemmatization"]:
            raise ValueError("Invalid method. Choose 'stemming' or 'lemmatization'.")
        
        nltk.download('wordnet') 
        nltk.download('omw-1.4')  

    def run(self, storage: DataFlowStorage, input_key: str):
        self.input_key = input_key
        self.logger.info(f"Running {self.__class__.__name__} with input_key = {self.input_key}...")
        dataframe = storage.read("dataframe")
        numbers = 0
        refined_data = []
        stemmer = PorterStemmer()
        lemmatizer = WordNetLemmatizer()
        for item in tqdm(dataframe[self.input_key], desc=f"Implementing {self.__class__.__name__}"):
            modified = False
            original_text = item
            
            if self.method == "stemming":
                refined_text = " ".join([stemmer.stem(word) for word in original_text.split()])
            elif self.method == "lemmatization":
                refined_text = " ".join([lemmatizer.lemmatize(word) for word in original_text.split()])

            if original_text != refined_text:
                item = refined_text
                modified = True
                self.logger.debug(f"Modified text for key '{self.input_key}': Original: {original_text[:30]}... -> Refined: {refined_text[:30]}...")

            refined_data.append(item)
            if modified:
                numbers += 1
                self.logger.debug(f"Item modified, total modified so far: {numbers}")
        self.logger.info(f"Refining Complete. Total modified items: {numbers}")
        dataframe[self.input_key] = refined_data
        output_file = storage.write(dataframe)
        return [self.input_key]