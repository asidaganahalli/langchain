import glob
import importlib
from pathlib import Path


def test_importable_all() -> None:
    for path in glob.glob("../community/langchain_community/*"):
        relative_path = Path(path).parts[-1]
        if relative_path.endswith(".typed"):
            continue
        module_name = relative_path.split(".")[0]
        if module_name == "runhouse":
            continue

        module = importlib.import_module("langchain_community." + module_name)
        all_ = getattr(module, "__all__", [])
        for cls_ in all_:
            getattr(module, cls_)
