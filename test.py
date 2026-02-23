import os
import sys
import shutil
import subprocess

TESS_EXE = "/usr/bin/tesseract"

def main():
    print("=== python ===")
    print("exe:", sys.executable)
    print("cwd:", os.getcwd())
    print("file:", os.path.abspath(__file__))

    print("\n=== which tesseract (PATH) ===")
    print("shutil.which:", shutil.which("tesseract"))

    print("\n=== check exe exists ===")
    print("exists:", os.path.exists(TESS_EXE))
    print("path:", TESS_EXE)

    print("\n=== run tesseract --version via subprocess ===")
    try:
        r = subprocess.run([TESS_EXE, "--version"], capture_output=True, text=True)
        print("returncode:", r.returncode)
        print("stdout:\n", r.stdout[:500])
        print("stderr:\n", r.stderr[:500])
    except Exception as e:
        print("subprocess exception:", repr(e))

if __name__ == "__main__":
    main()