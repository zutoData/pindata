import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer, AutoConfig
from huggingface_hub import PyTorchModelHubMixin
from dataflow.core import OperatorABC
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow.utils.storage import DataFlowStorage
from tqdm import tqdm
from dataflow import get_logger

@OPERATOR_REGISTRY.register()
class DebertaV3Scorer(OperatorABC):
    def __init__(self, model_name, model_cache_dir='./dataflow_cache', device='cuda'):
        self.logger = get_logger()
        self.logger.info(f'Initializing {self.__class__.__name__}...')
        self.model_name = model_name
        self.model_cache_dir = model_cache_dir
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.score_name = 'DebertaV3Score'
        self.config = AutoConfig.from_pretrained(self.model_name, cache_dir=self.model_cache_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=self.model_cache_dir)
        self.model = QualityModel.from_pretrained(self.model_name, cache_dir=self.model_cache_dir).to(self.device)
        self.model.eval()
        self.logger.info(f'{self.__class__.__name__} initialized.')

    def _score_func(self, sample):
        inputs = self.tokenizer(
            sample, return_tensors="pt", padding="longest", truncation=True
        ).to(self.device)
        with torch.no_grad():
            outputs = self.model(inputs["input_ids"], inputs["attention_mask"])
        predicted_classes = torch.argmax(outputs, dim=1)
        predicted_domains = [
            self.config.id2label[class_idx.item()] for class_idx in predicted_classes.cpu().numpy()
        ]
        return predicted_domains[0]  # Assuming one sample per batch

    def eval(self, dataframe, input_key):
        scores = []
        self.logger.info(f"Evaluating {self.score_name}...")
        for sample in tqdm(dataframe[input_key], desc="DebertaV3 modle evaluating..."):
            score = self._score_func(sample)
            scores.append(score)
        self.logger.info("Evaluation complete!")
        return scores

    def run(self, storage: DataFlowStorage, input_key: str, output_key: str='Debertav3Score'):
        self.input_key = input_key
        self.output_key = output_key
        dataframe = storage.read("dataframe")
        scores = self.eval(dataframe, input_key)
        dataframe[self.output_key] = scores
        storage.write(dataframe)


class QualityModel(nn.Module, PyTorchModelHubMixin):
    def __init__(self, config):
        super(QualityModel, self).__init__()
        self.model = AutoModel.from_pretrained(config["base_model"])
        self.dropout = nn.Dropout(config["fc_dropout"])
        self.fc = nn.Linear(self.model.config.hidden_size, len(config["id2label"]))

    def forward(self, input_ids, attention_mask):
        features = self.model(
            input_ids=input_ids, attention_mask=attention_mask
        ).last_hidden_state
        dropped = self.dropout(features)
        outputs = self.fc(dropped)
        return torch.softmax(outputs[:, 0, :], dim=1)
