from pathlib import Path


def get_gritdir_path():
    # TODO: include this in distribution
    script_dir = Path(__file__).parent
    return script_dir / ".grit"
