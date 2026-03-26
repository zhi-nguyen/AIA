import ast
import os

def check_syntax():
    """Checks syntax of all python files in the backend directory."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    has_errors = False
    
    for root, _, files in os.walk(backend_dir):
        # Bỏ qua thư mục venv/.*
        if any(part.startswith('.') or part == 'venv' or part == '__pycache__' for part in root.split(os.sep)):
            continue
            
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source, filename=filepath)
                except SyntaxError as e:
                    print(f"❌ Syntax Error in {os.path.relpath(filepath, backend_dir)}:")
                    print(f"   Line {e.lineno}: {e.msg}")
                    has_errors = True
                except Exception as e:
                    print(f"❌ Error reading {os.path.relpath(filepath, backend_dir)}: {e}")
                    has_errors = True
                    
    if not has_errors:
        print("✅ All Python files passed syntax check!")
        return 0
    return 1

if __name__ == "__main__":
    exit(check_syntax())
