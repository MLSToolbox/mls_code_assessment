import ast
import os
import sys
from typing import List, Dict, Set

# Mock PMCRAnalyzer parts to test logic in isolation
class MockPMCR:
    def __init__(self):
        self.ml_libraries = {'pandas', 'sklearn'}
        
    def _get_func_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_func_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        return ""

    def _extract_imports(self, tree: ast.Module) -> List[Dict]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'absolute', 
                        'name': alias.name,
                        'alias': alias.asname
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                level = node.level
                names = []
                aliases = []
                for n in node.names:
                    names.append(n.name)
                    aliases.append(n.asname)
                imports.append({
                    'type': 'from', 
                    'module': module, 
                    'level': level, 
                    'names': names,
                    'aliases': aliases
                })
        return imports

    def _extract_api_calls(self, tree: ast.Module, alias_map: Dict[str, str]) -> Set[str]:
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func)
                if func_name:
                    root = func_name.split('.')[0]
                    # Resolve alias if present
                    resolved_root = alias_map.get(root, root)
                    
                    # Check if the root library is in our ML list
                    lib_name = resolved_root.split('.')[0]
                    if lib_name in self.ml_libraries:
                        # Reconstruct full name with resolved root
                        parts = func_name.split('.')
                        parts[0] = resolved_root
                        full_name = '.'.join(parts)
                        calls.add(full_name)
        return calls

def test_strict_api_sharing():
    analyzer = MockPMCR()
    
    code_a = """
import pandas as pd
df = pd.read_csv('data.csv')
    """
    
    code_b = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2]})
    """
    
    code_c = """
import pandas as pd
df = pd.read_csv('other.csv')
    """
    
    def process_code(code):
        tree = ast.parse(code)
        imports = analyzer._extract_imports(tree)
        alias_map = {}
        for imp in imports:
            if imp['type'] == 'absolute':
                if imp.get('alias'):
                    alias_map[imp['alias']] = imp['name']
            elif imp['type'] == 'from':
                module = imp['module']
                for name, alias in zip(imp['names'], imp['aliases']):
                    full_name = f"{module}.{name}" if module else name
                    if alias:
                        alias_map[alias] = full_name
                    else:
                        alias_map[name] = full_name
        return analyzer._extract_api_calls(tree, alias_map)

    calls_a = process_code(code_a)
    calls_b = process_code(code_b)
    calls_c = process_code(code_c)
    
    print(f"Calls A: {calls_a}")
    print(f"Calls B: {calls_b}")
    print(f"Calls C: {calls_c}")
    
    shared_ab = calls_a & calls_b
    shared_ac = calls_a & calls_c
    
    print(f"Shared A-B (read_csv vs DataFrame): {shared_ab}")
    print(f"Shared A-C (read_csv vs read_csv): {shared_ac}")
    
    if not shared_ab:
        print("PASS: 'read_csv' and 'DataFrame' are correctly NOT considered shared API calls.")
    else:
        print("FAIL: 'read_csv' and 'DataFrame' SHOULD NOT be shared.")
        
    if 'pandas.read_csv' in shared_ac:
        print("PASS: 'read_csv' and 'read_csv' ARE considered shared API calls.")
    else:
        print("FAIL: 'read_csv' and 'read_csv' SHOULD be shared.")

if __name__ == "__main__":
    test_strict_api_sharing()
