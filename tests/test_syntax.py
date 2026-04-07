import ast
import glob


def test_all_python_files_have_valid_syntax():
    python_files = glob.glob("**/*.py", recursive=True)
    python_files = [f for f in python_files if "venv" not in f and "__pycache__" not in f]

    for file in python_files:
        # Read as bytes and decode using UTF-8 with replacement for undecodable
        # bytes so files containing emoji or non-UTF8 bytes don't cause the
        # test runner to crash with a UnicodeDecodeError. We still validate
        # syntax with ast.parse on the decoded source.
        with open(file, "rb") as f:
            raw = f.read()
        source = raw.decode("utf-8", errors="replace")
        try:
            ast.parse(source)
        except SyntaxError as e:
            assert False, f"Syntax error in {file}: {e}"
