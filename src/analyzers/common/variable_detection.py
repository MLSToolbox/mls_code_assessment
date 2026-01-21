"""
Variable and file detection utilities for structural cohesion analysis.

Provides functions to identify global variables, files accessed, and
method invocations in Python AST.
"""

import ast
from typing import Set, Dict


def is_likely_global_variable(var_name: str) -> bool:
    """
    Enhanced heuristic to determine if a variable is likely a global/module-level variable.
    
    Excludes:
    - Python builtins (list, dict, str, etc.)
    - Common imports (pd, np, os, etc.)
    - ML/Data Science type references (DataFrame, Tensor, ndarray, etc.)
    - Common local variable names
    
    Includes:
    - UPPERCASE names (constants)
    - _private names
    - MixedCase starting with uppercase (but excluding known types)
    - Common ML global patterns (data, model, scaler, etc.)
    
    Args:
        var_name: Variable name to check
        
    Returns:
        True if likely a global/module-level variable, False otherwise
    """
    # Python builtins
    builtins = {
        'list', 'dict', 'str', 'int', 'float', 'bool', 'len', 'print', 
        'range', 'enumerate', 'zip', 'set', 'min', 'max', 'sum', 'open',
        'tuple', 'bytes', 'bytearray', 'None', 'True', 'False',
        'object', 'type', 'callable', 'isinstance', 'issubclass'
    }
    
    # Common library aliases
    common_imports = {
        'np', 'pd', 'plt', 'sns', 'tf', 'torch', 'os', 'sys', 'json',
        'cv2', 'sk', 'sklearn', 'scipy', 'sp', 'math', 're', 'time',
        'datetime', 'collections', 'itertools', 'functools', 'operator',
        'pathlib', 'logging', 'warnings', 'pickle', 'joblib'
    }
    
    # ML/Data Science type references (often used as type hints or isinstance checks)
    ml_types = {
        # Pandas
        'DataFrame', 'Series', 'Index', 'MultiIndex', 'DatetimeIndex',
        'TimedeltaIndex', 'PeriodIndex', 'CategoricalIndex',
        # NumPy
        'ndarray', 'array', 'matrix', 'recarray', 'chararray',
        'dtype', 'int32', 'int64', 'float32', 'float64',
        # PyTorch
        'Tensor', 'LongTensor', 'FloatTensor', 'DoubleTensor',
        'Parameter', 'Module', 'Sequential', 'DataLoader', 'Dataset',
        # TensorFlow/Keras
        'Variable', 'constant', 'placeholder',
        # Sklearn
        'Pipeline', 'ColumnTransformer', 'StandardScaler', 'MinMaxScaler',
        'LabelEncoder', 'OneHotEncoder', 'Imputer', 'SimpleImputer',
        'RandomForestClassifier', 'LogisticRegression', 'SVC',
        # General ML
        'Model', 'Estimator', 'Transformer', 'Predictor', 'Classifier', 'Regressor'
    }
    
    # Common local variable names
    common_locals = {
        'result', 'results', 'output', 'temp', 'tmp', 'value', 'values',
        'item', 'items', 'elem', 'element', 'row', 'col', 'idx', 'index',
        'i', 'j', 'k', 'n', 'm', 'key', 'val', 'arg', 'args', 'kwargs',
        'self', 'cls', 'obj', 'func', 'fn', 'callback', 'handler'
    }
    
    # Exclude builtins, imports, types, and common locals
    if var_name in builtins or var_name in common_imports or var_name in ml_types or var_name in common_locals:
        return False
    
    # Common ML globals (actual data/model instances, not types)
    ml_globals = {
        'data', 'df', 'model', 'config', 'X', 'y', 
        'X_train', 'X_test', 'X_val',
        'y_train', 'y_test', 'y_val',
        'train_data', 'test_data', 'val_data',
        'scaler', 'encoder', 'tokenizer', 'vectorizer',
        'params', 'hyperparams', 'settings'
    }
    if var_name in ml_globals:
        return True
        
    # UPPERCASE (constants)
    if var_name.isupper() and len(var_name) > 1:
        return True
        
    # Starts with underscore (module-private)
    if var_name.startswith('_') and not var_name.startswith('__'):
        return True
        
    # MixedCase starting with uppercase (exclude if it's a known type pattern)
    if var_name[0].isupper() and not var_name.isupper():
        # Additional check: if it ends with common type suffixes, likely a type reference
        type_suffixes = ('Type', 'Class', 'Error', 'Exception', 'Warning')
        if any(var_name.endswith(suffix) for suffix in type_suffixes):
            return False
        return True
        
    return False


def get_files_accessed(method_node: ast.FunctionDef) -> Set[str]:
    """
    Detect file paths accessed by a method (datasets, models, configs).
    
    Scans string literals for ML-related file extensions:
    - Data files: .csv, .json, .parquet, .xlsx, .feather, etc.
    - Model files: .pkl, .h5, .pt, .ckpt, .pb, .onnx, etc.
    - Config files: .yaml, .yml, .ini, .cfg, .toml, etc.
    
    Args:
        method_node: AST FunctionDef node to analyze
        
    Returns:
        Set of file paths (strings) accessed by the method
        
    Example:
        For code: open('data/train.csv'), load('model.pkl')
        Returns: {'data/train.csv', 'model.pkl'}
    """
    # ML-related file extensions (19 total)
    ml_extensions = {
        # Data formats
        '.csv', '.json', '.parquet', '.xlsx', '.feather', '.arrow',
        '.tsv', '.txt', '.xml', '.avro', '.orc',
        # Model formats
        '.pkl', '.pickle', '.joblib', '.h5', '.hdf5', '.pt', '.pth',
        '.ckpt', '.model', '.pb', '.onnx', '.tflite', '.safetensors',
        # Config formats
        '.yaml', '.yml', '.ini', '.cfg', '.toml', '.conf',
        # NumPy formats
        '.npy', '.npz'
    }
    
    files = set()
    
    for node in ast.walk(method_node):
        # Look for string literals (ast.Constant with str value)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_value = node.value
            # Check if string contains any ML file extension
            for ext in ml_extensions:
                if ext in string_value.lower():
                    files.add(string_value)
                    break
    
    return files


def get_method_calls(
    method_node: ast.FunctionDef,
    all_methods: Dict[str, ast.FunctionDef]
) -> Set[str]:
    """
    Extract which other methods this method calls (for functional cohesion).
    
    Detects:
    - Direct function calls: my_function()
    - Method calls: self.my_method()
    - Qualified calls: ClassName.method_name()
    
    Args:
        method_node: AST FunctionDef node to analyze
        all_methods: Dictionary of all method names in the module
        
    Returns:
        Set of method names that this method invokes
        
    Example:
        For code in method 'execute': self.prepare(), validate()
        Returns: {'ClassName.prepare', 'validate'}
    """
    from analyzers.common.ast_utils import get_attribute_path
    
    calls = set()
    method_names = set(all_methods.keys())
    
    for node in ast.walk(method_node):
        if isinstance(node, ast.Call):
            func_name = _get_function_name(node.func)
            
            # Direct match
            if func_name in method_names:
                calls.add(func_name)
            # Match qualified name (e.g., "self.method" → "ClassName.method")
            elif '.' in func_name:
                parts = func_name.split('.')
                if len(parts) >= 2:
                    for full_name in method_names:
                        if full_name.endswith('.' + parts[-1]):
                            calls.add(full_name)
    
    return calls


def _get_function_name(func_node) -> str:
    """Extract function name from Call node."""
    from analyzers.common.ast_utils import get_attribute_path
    
    if isinstance(func_node, ast.Name):
        return func_node.id
    elif isinstance(func_node, ast.Attribute):
        return get_attribute_path(func_node)
    return ''
