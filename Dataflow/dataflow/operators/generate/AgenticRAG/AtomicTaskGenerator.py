from dataflow.prompts.agenticrag import AtomicTaskGeneratorPrompt
from dataflow.utils.registry import OPERATOR_REGISTRY
from dataflow  import get_logger
from dataflow.utils.storage import DataFlowStorage
from dataflow.core import OperatorABC
from dataflow.core import LLMServingABC

import pandas as pd
import json

@OPERATOR_REGISTRY.register()
class AtomicTaskGenerator(OperatorABC):
    def __init__(self,
                 llm_serving: LLMServingABC = None
                 ):
        self.logger= get_logger()
        self.prompts = AtomicTaskGeneratorPrompt()
        self.llm_serving = llm_serving

    @staticmethod
    def get_desc(self, lang):
        if lang == "zh":
            return (
            )
        elif lang == "en":
            return (
            )
        else:
            return
    
    def _validate_dataframe(self, dataframe: pd.DataFrame):
        required_keys = [self.input_key]
        forbidden_keys = [self.output_refined_answer_key, self.output_answer_key, self.output_question_key]

        missing = [k for k in required_keys if k not in dataframe.columns]
        conflict = [k for k in forbidden_keys if k in dataframe.columns]

        if missing:
            raise ValueError(f"Missing required column(s): {missing}")
        if conflict:
            raise ValueError(f"The following column(s) already exist and would be overwritten: {conflict}")

    def _reformat_prompt(self, dataframe, prompt_type: str = None):
        """
        Reformat the prompts in the dataframe to generate LLM input.
        All input columns are expected to be strings.
        """
        if prompt_type == "get_identifier":
            input_prompts = dataframe[self.input_key].tolist()
            system_prompt = self.prompts.get_identifier_system_prompt()
            prompts = [self.prompts.get_identifier_prompt(p) for p in input_prompts]

        elif prompt_type == "get_conclusion":
            input_prompts = dataframe[self.input_key].tolist()
            system_prompt = self.prompts.initial_conclusion_system_prompt()
            prompts = [self.prompts.initial_conclusion_prompt(p) for p in input_prompts]

        elif prompt_type == "init_question":
            candidate_strs = dataframe["candidate_tasks_str"].tolist()
            system_prompt = self.prompts.initial_question_system_prompt()
            prompts = []

            for s in candidate_strs:
                try:
                    item = json.loads(s)
                    prompts.append(self.prompts.initial_question_prompt(item['conclusion'], item['R']))
                except Exception as e:
                    print(f"[WARN] Failed to parse candidate_tasks_str: {e} | value: {s}")
                    prompts.append("")  # fallback to empty string or you can `continue`

        elif prompt_type == "clean_qa":
            questions = dataframe[self.output_question_key].tolist()
            answers = dataframe[self.output_answer_key].tolist()
            system_prompt = self.prompts.clean_qa_system_prompt()
            prompts = [
                self.prompts.clean_qa_prompt({"question": q, "original_answer": a})
                for q, a in zip(questions, answers)
            ]
        elif prompt_type == "llm_answer":
            questions = dataframe[self.output_question_key].tolist()
            system_prompt = ""
            prompts = [
                self.prompts.llm_answer_prompt(question) for question in questions
            ]
        elif prompt_type == "get_recall_score":
            golden_answers = dataframe[self.output_refined_answer_key].tolist()
            llm_answers = dataframe["llm_answer"]
            system_prompt = self.prompts.recall_system_prompt()
            prompts = [
                self.prompts.recall_prompt(golden_answer, llm_answer) for golden_answer, llm_answer in zip(golden_answers, llm_answers)
            ]
        else:
            raise ValueError(f"Unknown prompt_type: {prompt_type}")

        return system_prompt, prompts

    
    def _clean_json_block(self, item: str) -> str:
        return item.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    def recall_score(self, dataframe):
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "get_recall_score")
        recall_scores = self.llm_serving.generate_from_input(user_prompts, sys_prompts)
        valid_scores = []
        for score_str in recall_scores:
            if score_str is not None:
                try:
                    score_dict = json.loads(score_str)
                    valid_scores.append(score_dict["answer_score"])
                except (json.JSONDecodeError, KeyError):
                    print(score_str)
                    valid_scores.append(0)
                    continue
        return valid_scores
        
    def run(
        self,
        storage: DataFlowStorage,
        input_key: str = "prompts",
        output_question_key: str = "question",
        output_answer_key:str = "answer",
        output_refined_answer_key:str = "refined_answer"
    ):
        self.input_key, self.output_question_key = input_key, output_question_key
        self.output_answer_key, self.output_refined_answer_key = output_answer_key, output_refined_answer_key
        dataframe = storage.read("dataframe")
        self._validate_dataframe(dataframe)

        # === Step 0: Get identifier
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "get_identifier")
        identifiers = self.llm_serving.generate_from_input(user_prompts, sys_prompts)

        # === Step 1: Get conclusions
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "get_conclusion")
        conclusions = self.llm_serving.generate_from_input(user_prompts, sys_prompts)

        # === Expand each conclusion into multiple candidate tasks (rows)
        expanded_rows = []
        for idx, (row, output_str, identifier) in enumerate(zip(dataframe.itertuples(index=False), conclusions, identifiers)):
            try:
                parsed = json.loads(self._clean_json_block(output_str))
            except Exception as e:
                print(f"[WARN] JSON parse failed at idx={idx}: {e} | output: {output_str}")
                continue

            if not isinstance(parsed, list):
                continue

            for item in parsed:
                if isinstance(item, dict) and "conclusion" in item and "R" in item:
                    expanded_rows.append({
                        **row._asdict(),
                        "identifier": str(identifier),
                        "candidate_tasks_str": json.dumps(item, ensure_ascii=False)
                    })

        if not expanded_rows:
            self.logger.warning("No valid candidate tasks extracted.")
            return

        dataframe = pd.DataFrame(expanded_rows)

        # === Step 2: Generate questions based on conclusion+reasoning
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "init_question")
        question_outputs = self.llm_serving.generate_from_input(user_prompts, sys_prompts)

        questions = []
        answers = []
        valid_rows = []

        for idx, (res, row) in enumerate(zip(question_outputs, dataframe.itertuples(index=False))):
            try:
                parsed = json.loads(res)
            except Exception as e:
                print(f"[WARN] Failed to parse question JSON at idx={idx}: {e} | res: {res}")
                continue

            if isinstance(parsed, dict) and "Q" in parsed:
                question = parsed["Q"]
                try:
                    task = json.loads(row.candidate_tasks_str)
                    answer = task.get("conclusion", "")
                except Exception:
                    answer = ""
                valid_rows.append(row._asdict())
                questions.append(str(question))
                answers.append(str(answer))

        if not valid_rows:
            self.logger.warning("No valid QA pairs generated.")
            return

        dataframe = pd.DataFrame(valid_rows)
        dataframe[self.output_question_key] = questions
        dataframe[self.output_answer_key] = answers

        # === Step 3: Clean QA
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "clean_qa")
        clean_outputs = self.llm_serving.generate_from_input(user_prompts, sys_prompts)

        final_answers = []

        for idx, res in enumerate(clean_outputs):
            try:
                parsed = json.loads(res)
                final_answers.append(str(parsed.get("refined_answer", "")))
            except Exception as e:
                print(f"[WARN] Failed to parse cleaned QA at idx={idx}: {e} | res: {res}")
                final_answers.append("")

        dataframe[self.output_refined_answer_key] = final_answers

        # Verify module
        sys_prompts, user_prompts = self._reformat_prompt(dataframe, "llm_answer")
        llm_answer_results = self.llm_serving.generate_from_input(user_prompts, sys_prompts)

        dataframe["llm_answer"] = llm_answer_results
        llm_score = self.recall_score(dataframe)
        dataframe["llm_score"] = llm_score
        dataframe = dataframe[dataframe["llm_score"] < 1].drop(columns=["llm_score"]).reset_index(drop=True)
        dataframe = dataframe.drop(columns="llm_answer")

        output_file = storage.write(dataframe)
        self.logger.info(f"Results saved to {output_file}")
        return "identifier", "candidate_tasks_str", self.output_question_key, self.output_answer_key, self.output_refined_answer_key