import re
from tqdm import tqdm
from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY

@OPERATOR_REGISTRY.register()
class ReferenceRemoverRefiner(OperatorABC):
    def __init__(self):
        self.logger = get_logger()
        self.logger.info(f"Initializing {self.__class__.__name__}...")

    @staticmethod
    def get_desc(lang):
        return "删除文本中未闭合的引用标签和引用链接" if lang == "zh" else "Remove unclosed reference tags and citation links from the text."

    def run(self, storage: DataFlowStorage, input_key: str):
        self.input_key = input_key
        dataframe = storage.read("dataframe")
        self.logger.info(f"Running {self.__class__.__name__} with input_key = {self.input_key}...")
        numbers = 0
        # 定义要删除的模式 - 更全面的版本
        # 1. 所有<ref>标签及其内容(包括各种不完整形式)
        ref_pattern = re.compile(
            r'<ref\b[^>]*>.*?</ref>|'  # 完整的ref标签
            r'<ref\b[^>]*>[^<]*$|'     # 不完整的ref标签(没有闭合)
            r'<ref\b[^>]*>.*?/br'      # ref标签后跟/br(如你示例中的情况)
        )
        
        # 2. 所有{{cite}}模板及其内容(包括各种不完整形式)
        cite_pattern = re.compile(
            r'\{\{cite\s+\w+\|[^}]*\}\}|'  # 完整的cite模板
            r'\{\{cite\s+\w+\|[^}]*$'      # 不完整的cite模板(没有闭合)
        )

        refined_data = []
        for item in tqdm(dataframe[self.input_key], desc=f"Implementing {self.__class__.__name__}"):
            modified = False  
            original_text = item
            refined_text = original_text

            # 删除所有未闭合的ref标签
            refined_text, ref_count = ref_pattern.subn('', refined_text)
            
            # 删除所有不完整的cite模板
            refined_text, cite_count = cite_pattern.subn('', refined_text)

            # 检查是否有任何修改
            if ref_count > 0 or cite_count > 0:
                modified = True
                numbers += 1
                self.logger.debug(f"Item modified, removed {ref_count} ref tags and {cite_count} cite templates")

            refined_data.append(item)
            if modified:
                numbers += 1
                self.logger.debug(f"Item modified, total modified so far: {numbers}")
        self.logger.info(f"Refining Complete. Total modified items: {numbers}")
        dataframe[self.input_key] = refined_data
        output_file = storage.write(dataframe)
        return [self.input_key]