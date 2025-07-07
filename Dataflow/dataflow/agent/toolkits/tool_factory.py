from typing import Callable, Any, Dict, List, Union
from pathlib import Path

class Tool:
    def __init__(self, name: str, func: Callable, type_: str = "local", desc: str = ""):
        self.name = name
        self.func = func
        self.type = type_
        self.desc = desc

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, name: str, func: Callable, type_: str = "local", desc: str = ""):
        if name in self.tools:
            # raise ValueError(f"Tool '{name}' already registered.")
            return
        self.tools[name] = Tool(name, func, type_, desc)

    def get(self, name: str) -> Tool:
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found.")
        return self.tools[name]

    def call(self, name: str, *args, **kwargs):
        tool = self.get(name)
        return tool(*args, **kwargs)

    def list_tools(self, type_: str = None):
        if type_:
            return [tool for tool in self.tools.values() if tool.type == type_]
        return list(self.tools.values())

    def register_tool_list(self, tool_list, type_: str = "local"):
        """
        批量注册工具函数列表，tool_list 元素为 (name, func, desc)
        """
        for name, func, desc in tool_list:
            self.register(name, func, type_=type_, desc=desc)

    def tools_info_as_json(self) -> str:
        import json
        tools_info = [
            {"name": tool.name, "desc": tool.desc}
            for tool in self.tools.values()
        ]
        return json.dumps(tools_info, ensure_ascii=False, indent=2)