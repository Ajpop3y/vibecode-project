import os
import ast
import sys

def check_docstrings(start_path):
    missing_docs = []
    print(f"Scanning {start_path} for python modules...")
    
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, start_path)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    if not content.strip():
                        # Empty files like __init__.py are okay if truly empty
                        if file == "__init__.py":
                            continue
                        else:
                            print(f"[WARN] Empty file: {rel_path}")
                            continue

                    tree = ast.parse(content)
                    docstring = ast.get_docstring(tree)
                    
                    if not docstring:
                        # Special check: Does it have a hash-bang or encoding cookie at top?
                        # AST docstring must be first statement.
                        missing_docs.append(rel_path)
                    
                except Exception as e:
                    print(f"[ERROR] Parsing {rel_path}: {e}")

    return missing_docs

if __name__ == "__main__":
    if len(sys.argv) > 1:
        src_path = sys.argv[1]
    else:
        # Default to src/vibecode
        src_path = os.path.join(os.getcwd(), "src", "vibecode")
    
    if not os.path.isdir(src_path):
        print(f"Directory not found: {src_path}")
        sys.exit(1)

    missing = check_docstrings(src_path)
    
    print("-" * 40)
    if missing:
        print(f"Found {len(missing)} modules missing docstrings:")
        for m in missing:
            print(f" [MISSING] {m}")
        sys.exit(1)
    else:
        print("✅ SUCCESS: All modules have docstrings!")
        sys.exit(0)
