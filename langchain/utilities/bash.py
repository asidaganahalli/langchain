"""Wrapper around subprocess to run commands."""
import subprocess
from typing import List


class BashProcess:
    """Executes bash commands and returns the output."""

    def __init__(self, strip_newlines: bool = False):
        """Initialize with stripping newlines."""
        self.strip_newlines = strip_newlines

    def run(self, commands: List[str]) -> str:
        """Run commands and return final output."""
        outputs = []
        for command in commands:
            try:
                output = subprocess.check_output(command, shell=True).decode()
                if self.strip_newlines:
                    output = output.strip()
                outputs.append(output)
            except subprocess.CalledProcessError as error:
                return str(error)
        return outputs[-1]
