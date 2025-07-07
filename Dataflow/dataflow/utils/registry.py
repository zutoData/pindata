import importlib
import importlib.util
import types
import os
from dataflow.logger import get_logger
from pathlib import Path

from rich.console import Console
from rich.table import Table

class Registry():
    """
    The registry that provides name -> object mapping, to support third-party
    users' custom modules.

    To create a registry (e.g. a backbone registry):

    .. code-block:: python

        BACKBONE_REGISTRY = Registry('BACKBONE')

    To register an object:

    .. code-block:: python

        @BACKBONE_REGISTRY.register()
        class MyBackbone():
            ...

    Or:

    .. code-block:: python

        BACKBONE_REGISTRY.register(MyBackbone)
    """

    def __init__(self, name):
        """
        Args:
            name (str): the name of this registry
        """
        self._name = name
        self._obj_map = {}

    def _do_register(self, name, obj):
        if name not in self._obj_map:
            self._obj_map[name] = obj

    def register(self, obj=None):
        """
        Register the given object under the the name `obj.__name__`.
        Can be used as either a decorator or not.
        See docstring of this class for usage.
        """
        if obj is None:
            # used as a decorator
            def deco(func_or_class):
                name = func_or_class.__name__
                self._do_register(name, func_or_class)
                return func_or_class

            return deco

        # used as a function call
        name = obj.__name__
        self._do_register(name, obj)

    def get(self, name):
        ret = self._obj_map.get(name)
        logger = get_logger()
        if ret is None:
            if self._name == 'operator': 
                for x in ['eval', 'generate', 'process', 'refine']:
                    module_path = "dataflow.operators." + x
                    try:
                        module_lib = importlib.import_module(module_path)
                        clss = getattr(module_lib, name)
                        self._obj_map[name] = clss
                        return clss
                    except AttributeError as e:
                        logger.debug(f"{str(e)}")
                        continue
                    except Exception as e:
                        raise e
                logger.error(f"No object named '{name}' found in '{self._name}' registry!")
                raise KeyError(f"No object named '{name}' found in '{self._name}' registry!")

        if ret is None:
            logger.error(f"No object named '{name}' found in '{self._name}' registry!")
        assert ret is not None, f"No object named '{name}' found in '{self._name}' registry!"
        
        return ret

    def __contains__(self, name):
        return name in self._obj_map

    def __iter__(self):
        return iter(self._obj_map.items())

    def keys(self):
        return self._obj_map.keys()

    def __repr__(self):
        table = Table(title=f'Registry of {self._name}')
        table.add_column('Names', justify='left', style='cyan')
        table.add_column('Objects', justify='left', style='green')

        for name, obj in sorted(self._obj_map.items()):
            table.add_row(name, str(obj))

        console = Console()
        with console.capture() as capture:
            console.print(table, end='')

        return capture.get()

    def get_obj_map(self):
        """
        Get the object map of the registry.
        """
        return self._obj_map

OPERATOR_REGISTRY = Registry('operator')
class LazyLoader(types.ModuleType):

    def __init__(self, name, path, import_structure):
        """
        初始化 LazyLoader 模块。

        :param name: 模块名称
        :param import_structure: 定义类名到文件路径的映射字典
        """
        super().__init__(name)
        self._import_structure = import_structure
        self._loaded_classes = {}
        self._base_folder = Path(__file__).resolve().parents[2]
        self.__path__ = [path]

    def _load_class_from_file(self, file_path, class_name):
        """
        从指定文件中加载类。

        :param file_path: 脚本文件的路径
        :param class_name: 类的名字
        :return: 类对象
        """
        abs_file_path = os.path.join(self._base_folder, file_path)
        if not os.path.exists(abs_file_path):
            raise FileNotFoundError(f"File {abs_file_path} does not exist")
        logger = get_logger()
        # 动态加载模块
        try:
            spec = importlib.util.spec_from_file_location(class_name, abs_file_path)
            logger.debug(f"LazyLoader {self.__path__} successfully imported spec {spec.__str__()}")
            module = importlib.util.module_from_spec(spec)
            logger.debug(f"LazyLoader {self.__path__} successfully imported module {module.__str__()} from spec {spec.__str__()}")
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"{e.__str__()}")
            raise e

        # 提取类
        if not hasattr(module, class_name):
            raise AttributeError(f"Class {class_name} not found in {abs_file_path}")
        return getattr(module, class_name)

    def __getattr__(self, item):
        """
        动态加载类。

        :param item: 类名
        :return: 动态加载的类对象
        """
        logger = get_logger()
        if item in self._loaded_classes:
            cls = self._loaded_classes[item]
            logger.debug(f"Lazyloader {self.__path__} got cached class {cls}")
            return cls
        # 从映射结构中获取文件路径和类名
        if item in self._import_structure:
            file_path, class_name = self._import_structure[item]
            logger.info(f"Lazyloader {self.__path__} trying to import {item} ")
            cls = self._load_class_from_file(file_path, class_name)
            logger.debug(f"Lazyloader {self.__path__} got and cached class {cls}")
            self._loaded_classes[item] = cls
            return cls
        logger.debug(f"Module {self.__name__} has no attribute {item}")
        raise AttributeError(f"Module {self.__name__} has no attribute {item}")
