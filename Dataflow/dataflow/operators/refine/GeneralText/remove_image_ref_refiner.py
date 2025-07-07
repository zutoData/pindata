import re
from tqdm import tqdm
from dataflow import get_logger
from dataflow.core import OperatorABC
from dataflow.utils.storage import DataFlowStorage
from dataflow.utils.registry import OPERATOR_REGISTRY

@OPERATOR_REGISTRY.register()
class RemoveImageRefsRefiner(OperatorABC):
    def __init__(self):
        self.logger = get_logger()
        self.image_pattern = re.compile(
            r'!\[\]\(images\/[0-9a-fA-F]\.jpg\)|'
            r'[a-fA-F0-9]+\.[a-zA-Z]{3,4}\)|'
            r'!\[\]\(images\/[a-f0-9]|'
            r'图\s+\d+-\d+：[\u4e00-\u9fa5a-zA-Z0-9]+|'
            r'(?:[0-9a-zA-Z]+){7,}|'                # 正则5
            r'(?:[一二三四五六七八九十零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+){5,}|'  # 正则6（汉字数字）
            r"u200e|"
            r"&#247;|\? :|"
            r"[�□]|\{\/U\}|"
            r"U\+26[0-F][0-D]|U\+273[3-4]|U\+1F[3-6][0-4][0-F]|U\+1F6[8-F][0-F]"
        )
        self.logger.info(f"Initializing {self.__class__.__name__} ...")

    @staticmethod
    def get_desc(lang: str = "zh"):
        return "去除文本中的图片引用" if lang == "zh" else "Remove image references in text."

    def run(self, storage: DataFlowStorage, input_key: str):
        self.input_key = input_key
        dataframe = storage.read("dataframe")
        self.logger.info(f"Running {self.__class__.__name__} with input_key = {self.input_key}...")
        numbers = 0
        refined_data = []
        for item in tqdm(dataframe[self.input_key], desc=f"Implementing {self.__class__.__name__}"):
            modified = False
            original_text = item
            # 移除所有图片引用格式[1,2](@ref)
            cleaned_text = self.image_pattern.sub('', original_text)
            
            if original_text != cleaned_text:
                item = cleaned_text
                modified = True
                # 调试日志：显示修改前后的对比
                self.logger.debug(f"Modified text for key '{self.input_key}':")
                self.logger.debug(f"Original: {original_text[:100]}...")
                self.logger.debug(f"Refined : {cleaned_text[:100]}...")

            refined_data.append(item)
            if modified:
                numbers += 1
                self.logger.debug(f"Item modified, total modified so far: {numbers}")
        self.logger.info(f"Refining Complete. Total modified items: {numbers}")
        dataframe[self.input_key] = refined_data
        output_file = storage.write(dataframe)
        return [self.input_key]