import ast
import glob

def test_all_python_files_have_valid_syntax():    
    python_files = glob.glob('**/*.py', recursive=True)
    python_files = [f for f in python_files 
                    if 'venv' not in f and '__pycache__' not in f]
    
    for file in python_files:
        with open(file, 'r') as f:
            try:
                ast.parse(f.read())
            except SyntaxError as e:
                assert False, f"Syntax error in {file}: {e}"