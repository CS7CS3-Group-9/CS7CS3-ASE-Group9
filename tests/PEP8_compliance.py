import pycodestyle
import glob


def test_pep8_conformance():
    """Test all Python files using pycodestyle."""
    style_guide = pycodestyle.StyleGuide(
        ignore=[
            "E501",  # ignore line length if desired
        ],
        max_line_length=120,
    )

    python_files = glob.glob("**/*.py", recursive=True)
    python_files = [
        f for f in python_files if "venv" not in f and "__pycache__" not in f
    ]

    result = style_guide.check_files(python_files)
    assert result.total_errors == 0, f"Found PEP8 errors: {result.total_errors}"
