'''
A collection of prompts for the general text operator.
'''
class PretrainGeneratorPrompt:
    
    def __init__(self):
        pass
    
    def pt_generate_prompt(self, content: str) -> str:
        """
        Generate the LLM input prompt by inserting the raw content into the prompt template.
        """
        prompt = """
        A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polite answers to the questions. 
        Convert the following paragraph into a conversational format with multiple tags of "Question:" followed by "Answer:":

        You can only output as the given format:
        Question: xxx Answer: xxx
        Question: xxx Answer: xxx
        Now please covert the content below.
        {content}
        """
        return prompt.format(content=content)
    
class SupervisedFinetuneGeneratorPrompt:
    
    def __init__(self):
        pass

    def sft_generate_prompt(self, num_questions: int = 1, content: str = "") -> str:
        """
        Generate the LLM input prompt by inserting the raw content into the prompt template.
        """
        prompt = """You are tasked with creating high-quality SFT data for LLM training. Please generate a batch of data where the only task is to create questions based on the provided context. Focus on diversity, relevance, and clarity when forming the questions. Please ensure each question is distinct and appropriately aligned with the context.
        Your Questions must meet the following requirements:
        1. You must strictly create exactly {num_questions} questions at a time.
        2. These {num_questions} questions must cover different aspects of the topic, ensuring diversity and comprehensiveness.
        3. Each question should be framed based on the provided context and should include sufficient background information. The questions should not be abrupt or vague.
        4. Please output the {num_questions} questions in the following JSON format:
        {{
            "instruction": "QUESTION",
            "output": "ANSWER"
        }}
        5. Here are some examples of high-quality SFT data questions with completed outputs:
        {{
            "instruction": "Can you provide a list of healthy habits to maintain a healthy lifestyle? Please format your response as an HTML page with bullet points.",
            "output": "Here's an HTML page with bullet points for healthy habits: <html><body><h3>Healthy Habits:</h3><ul><li>Eating a balanced diet with plenty of fruits and vegetables.</li><li>Engaging in regular physical activity, such as walking, running, or cycling.</li><li>Getting enough sleep each night, ideally 7-8 hours.</li><li>Staying hydrated by drinking plenty of water throughout the day.</li><li>Limiting alcohol consumption and avoiding smoking.</li><li>Managing stress through relaxation techniques like meditation or yoga.</li><li>Regularly visiting a healthcare provider for check-ups and preventative care.</li></ul></body></html>"
        }},
        {{
            "instruction": "How can we use Python to calculate the GCD (greatest common divisor) of five numbers and express each number in terms of the GCD?",
            "output": "Here's a Python function that calculates the GCD of five numbers: def find_gcd(a, b, c, d, e): smallest = min(a, b, c, d, e) while True: if all(x % smallest == 0 for x in [a, b, c, d, e]): return smallest else: smallest -= 1. This will compute the GCD and can express each number in terms of the GCD."
        }},
        {{
            "instruction": "Generate a list of ten essential items a person might need for a camping trip, considering the weather, terrain, and local wildlife. Provide a breakdown of weight, size, and functionality of each item.",
            "output": "Here's a list of ten essential items for a camping trip: 1. Tent - lightweight, easy to set up, weighs 3.5 pounds, $450. 2. Sleeping bag - keeps you warm at 20°F, weighs 2 pounds, $200. 3. Sleeping pad - insulates and cushions, weighs 1 pound, $100. 4. Backpack - 65L capacity, weighs 4.5 pounds, $250. 5. Water filter - lightweight, filters up to 100,000 gallons, $40. 6. Headlamp - bright, 300 lumens, $30. 7. Multi-tool - versatile, 18 tools, $80. 8. Stove - boils water in 2 minutes, $100. 9. Bear canister - stores food securely, $70. 10. First aid kit - essential medical supplies, $50."
        }}
        6. Now it's your turn. You can use your rich imagination, but note that you cannot copy the expression from the examples; you must have your own new expression:

        Please create {num_questions} distinct and well-formed questions based on the following context:""".format(num_questions=num_questions)
        return f"<|im_start|>system\n{prompt}<|im_end|>\n<|im_start|>user\n{content}<|im_end|>\n<|im_start|>assistant"

class AlpagasusPrompt:
    def __init__(self, dimension='quality'):
        self.dimension = dimension
        self.system_prompt_template = """
        We would like to request your feedback on the performance of AI assistant in response to the instruction and the given input displayed following.
        Instruction: {instruction}
        Input: {input}
        Response: {response}
        """
        self.user_prompt_template = """
        Please rate according to the {dimension} of the response to the instruction and the input. Each assistant
        receives a score on a scale of 0 to 5, where a higher score indicates a higher level of the {dimension}. Please
        first output a single line containing the value indicating the scores. In the subsequent line, please provide a comprehensive explanation of your evaluation, avoiding any potential bias.
        """

    def build_system_prompt(self, instruction, input_text, response):
        """
        生成system prompt
        """
        return self.system_prompt_template.format(instruction=instruction, input=input_text, response=response)

    def build_user_prompt(self):
        """
        生成user prompt
        """
        return self.user_prompt_template.format(dimension=self.dimension)

class TreeinstructPrompt:
    def __init__(self):
        self.system_prompt_template = """
        You are an instruction rewriter. You need to parse a given user instruction into a TREE structure following Semantic Parsing in the natural language processing field.
        Procedure:
        step-1: Parse the old “instruction” to a TREE-1 through Semantic Parsing in the natural language processing field. 
        Count and return the number of nodes in TREE-1.
        Old instruction: “{instruction}”
        """

        self.user_prompt_template = """
        Please count and return the number of nodes in TREE-1. This number represents the complexity of the original instruction.
        Output the number in the single LAST line. You must ensure the last line is only the number of the tree, without other symbols, like ```.
        For example:
        4
        """
    
    def build_system_prompt(self, instruction):
        """
        根据给定的指令生成 system prompt
        """
        return self.system_prompt_template.format(instruction=instruction)
    
    def build_user_prompt(self):
        """
        生成 user prompt
        """
        return self.user_prompt_template
