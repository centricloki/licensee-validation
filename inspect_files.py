import os

def list_files(startpath):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            fp = os.path.join(root, f)
            size = os.path.getsize(fp)
            print(f"{subindent}{f} ({size} bytes)")

print("Files in distributors:")
list_files("distributors")
