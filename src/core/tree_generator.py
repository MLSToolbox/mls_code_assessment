import os
import ast
from typing import Dict, List


class TreeGenerator:
    """Generates hierarchical file tree structure."""
    
    EXCLUDED_PATTERNS = {
        '__pycache__', '.git', '.pyc', '.pyo', '.pyd',
        'node_modules', 'venv', 'env', '.vscode', '.idea',
        '.DS_Store', 'Thumbs.db', '.pytest_cache', '__MACOSX'
    }
    
    def __init__(self, root_path: str):
        """
        Initialize TreeGenerator.
        
        Args:
            root_path: Root directory path
        """
        self.root_path = root_path
    
    def generate(self) -> Dict:
        """
        Generate file tree structure.
        
        Returns:
            Dictionary representing file tree
        """
        return self._build_tree(self.root_path, "/")
    
    def _build_tree(self, path: str, relative_path: str) -> Dict:
        """
        Recursively build tree structure.
        
        Args:
            path: Absolute path
            relative_path: Relative path from root
            
        Returns:
            Tree node dictionary
        """
        name = os.path.basename(path) or os.path.basename(self.root_path)
        
        node = {
            "name": name,
            "path": relative_path,
            "type": "directory" if os.path.isdir(path) else "file"
        }
        
        if os.path.isfile(path):
            node["size"] = os.path.getsize(path)
            
            if path.endswith('.py'):
                node["valid_syntax"] = self._is_valid_python(path)
        else:
            children = []
            
            try:
                entries = sorted(os.listdir(path))
                
                for entry in entries:
                    if self._should_exclude(entry):
                        continue
                    
                    entry_path = os.path.join(path, entry)
                    entry_relative = os.path.join(relative_path, entry)
                    
                    child_node = self._build_tree(entry_path, entry_relative)
                    children.append(child_node)
                
            except PermissionError:
                pass  # Skip directories we can't read
            
            if children:
                node["children"] = children
        
        return node
    
    def _should_exclude(self, name: str) -> bool:
        """
        Check if file/directory should be excluded.
        
        Args:
            name: File or directory name
            
        Returns:
            True if should be excluded
        """
        if name in self.EXCLUDED_PATTERNS:
            return True
        
        for pattern in self.EXCLUDED_PATTERNS:
            if pattern in name:
                return True
        
        return False
    
    def _is_valid_python(self, filepath: str) -> bool:
        """
        Validate Python file syntax.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            True if syntax is valid
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            return True
        except (SyntaxError, UnicodeDecodeError):
            return False