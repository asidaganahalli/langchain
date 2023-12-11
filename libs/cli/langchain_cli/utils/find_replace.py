from typing import Dict
from pathlib import Path


def find_and_replace(source: str, replacements: Dict[str, str]) -> str:
    rtn = source

    # replace keys in deterministic alphabetical order
    finds = sorted(replacements.keys())
    for find in finds:
        replace = replacements[find]
        rtn = rtn.replace(find, replace)
    return rtn


def replace_file(source: Path, replacements: Dict[str, str]) -> None:
    with open(source, "r+") as f:
        f.write(find_and_replace(f.read(), replacements))
