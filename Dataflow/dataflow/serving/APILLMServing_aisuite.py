import logging
import aisuite as ai
import pandas as pd
from tqdm import tqdm
from dataflow.core import LLMServingABC
from dataflow.utils.storage import FileStorage
from typing import List

class APILLMServing_aisuite(LLMServingABC):
    def __init__(self, config: dict):
        configs = config  # Assuming config.configs is a list of configurations

        # Extract the configurations from the provided dictionary
        self.model_id = configs.get("model_id", 'openai:gpt-4o')
        self.temperature = configs.get("temperature", 0.75)
        self.top_p = configs.get("top_p", 1)
        self.max_tokens = configs.get("max_tokens", 20)
        self.n = configs.get("n", 1)
        self.stream = configs.get("stream", False)
        self.stop = configs.get("stop", None)
        self.presence_penalty = configs.get("presence_penalty", 0)
        self.frequency_penalty = configs.get("frequency_penalty", 0)
        self.logprobs = configs.get("logprobs", None)
        self.system_prompt = configs.get("system_prompt", "You are a helpful assistant")
        
        # Input and output file paths and keys
        self.datastorage = FileStorage(configs)
        

        logging.info(f"API Generator will generate text using {self.model_id}")
    
    def generate(self):
        # check config
        

        client = ai.Client()
        outputs = []

        # Read input file
        dataframe = self.datastorage.read(self.input_file, "dataframe")
        
        # Check if input_key is in the dataframe
        if self.input_key not in dataframe.columns:
            key_list = dataframe.columns.tolist()
            raise ValueError(f"input_key: {self.input_key} not found in the dataframe, please check the input_key: {key_list}")
        
        # Check if output_key is in the dataframe
        if self.output_key in dataframe.columns:
            key_list = dataframe.columns.tolist()
            raise ValueError(f"Found {self.output_key} in the dataframe, which leads to overwriting the existing column, please check the output_key: {key_list}")
        
        # Generate text
        user_prompts = dataframe[self.input_key].tolist()
        for user_prompt in user_prompts:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                n=self.n,
                stream=self.stream,
                stop=self.stop,
                logprobs=self.logprobs,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty,
            )
            content = response.choices[0].message.content
            outputs.append(content)
        dataframe[self.output_key] = outputs
        self.datastorage.write(self.output_file, dataframe)
        return dataframe

    def generate_from_input(self, input: List[str]) -> List[str]:
        client = ai.Client()
        outputs = []

        for question in tqdm(input, desc="Generating......"):
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question}
            ]
            response = client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                n=self.n,
                stream=self.stream,
                stop=self.stop,
                logprobs=self.logprobs,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty,
            )
            content = response.choices[0].message.content
            outputs.append(content)

        return outputs

    def cleanup(self):
        # Cleanup resources if needed
        logging.info("Cleaning up resources in APILLMServing_aisuite")
        # No specific cleanup actions needed for this implementation
        pass