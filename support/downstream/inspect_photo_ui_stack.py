import importlib.util
for name in ['PySide6','PyQt6','PyQt5','customtkinter','webview']:
    print(name, bool(importlib.util.find_spec(name)),flush=True)
