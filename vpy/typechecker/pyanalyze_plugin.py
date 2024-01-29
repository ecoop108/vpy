from ast import ClassDef, FunctionDef, Module
from logging import CRITICAL
from typing import Any, Mapping, Optional
from pyanalyze.name_check_visitor import NameCheckVisitor, ClassAttributeChecker
from vpy.lib.lib_types import Environment
from vpy.lib.lookup import methods_lookup
from enum import Enum
from vpy.lib.utils import get_at, graph, is_obj_attribute, typeof_node


class TypeCheckerVisitor(ClassAttributeChecker):
    pass
