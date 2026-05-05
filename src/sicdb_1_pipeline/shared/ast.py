import ast
import math
from typing import Iterable, Any, List

ALLOWED_NODES = (
    ast.Module,
    ast.Assign,
    ast.Return,
    ast.If,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,

    ast.Expr,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Attribute,

    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,

    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub,

    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


class Validator(ast.NodeVisitor):
    def visit(self, node):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"Illegal syntax: {type(node).__name__}")
        super().visit(node)

    def visit_Name(self, node):
        if node.id not in {"value", "math"}:
            raise ValueError(f"Illegal variable: {node.id}")

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Attribute):
            raise ValueError("Only math.xxx() calls allowed")
        if not isinstance(node.func.value, ast.Name):
            raise ValueError("Illegal function call")
        if node.func.value.id != "math":
            raise ValueError("Only math module allowed")
        self.generic_visit(node)

def compile_transform(code: str):
    if not code or not isinstance(code, str):
        raise ValueError("code must be a non-empty string")


    fn_src = f"""
def __transform__(value):
{indent(code, "    ")}
"""
    tree = ast.parse(fn_src, mode="exec")
    Validator().visit(tree)

    compiled = compile(tree, "<transform>", "exec")

    env = {"__builtins__": {}, "math": math}
    exec(compiled, env)

    return env["__transform__"]


def indent(src: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in src.splitlines())




async def try_transform_code_async(code: str, samples: Iterable[Any]) -> List[Any]:
    transform = compile_transform(code)

    return [transform(value) for value in samples]




