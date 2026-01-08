"""
Common AST utilities shared across analyzers.

Provides reusable functions for AST manipulation and method extraction.
"""

import ast
from typing import Dict


def extract_methods(tree: ast.Module) -> Dict[str, ast.FunctionDef]:
    """
    Extract all methods/functions from an AST, with qualified names.
    
    Functions at module level get their name as-is.
    Methods inside classes get qualified names: ClassName.method_name
    
    Args:
        tree: AST Module node
        
    Returns:
        Dictionary mapping qualified method names to FunctionDef nodes
        
    Example:
        {
            'prepare_data': <FunctionDef node>,
            'MyClass.__init__': <FunctionDef node>,
            'MyClass.process': <FunctionDef node>
        }
    """
    class MethodVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None
            self.methods = {}
        
        def visit_ClassDef(self, node):
            old_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = old_class
        
        def visit_FunctionDef(self, node):
            if self.current_class:
                method_name = f"{self.current_class}.{node.name}"
            else:
                method_name = node.name
            self.methods[method_name] = node
            # Don't visit nested functions - only top-level methods
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, ast.FunctionDef):
                    self.visit(child)
    
    visitor = MethodVisitor()
    visitor.visit(tree)
    return visitor.methods


def get_attribute_path(node: ast.Attribute) -> str:
    """
    Extract full attribute path from an Attribute node.
    
    Handles nested attributes like:
    - self.data -> "self.data"
    - obj.method.result -> "obj.method.result"
    
    Args:
        node: ast.Attribute node
        
    Returns:
        Dot-separated attribute path string
        
    Example:
        For ast.Attribute representing "self.config.path":
        Returns: "self.config.path"
    """
    parts = []
    current = node
    
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return '.'.join(reversed(parts))
    
    return ''
