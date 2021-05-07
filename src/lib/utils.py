import re
import subprocess as sp
from fileinput import FileInput
from sys import exit
from typing import Optional


def handle_sigint(signal: int, frame: Optional[object]):
    exit(1)


def run(cmd: str, *, capture_output: bool = False) -> sp.CompletedProcess:
    capture_args = {'stdout': sp.PIPE} if capture_output else {}

    return sp.run(cmd.split(), check=True, text=True, stderr=sp.STDOUT, **capture_args)


def write_to_file(file_path: str, content: str) -> None:
    with open(file_path, mode='w') as file:
        print(content.strip(), file=file)


def replace_in_file(file_path: str, search_pattern: str, replacement: str) -> None:
    with FileInput(file_path, inplace=True) as file:
        for line in file:
            print(re.sub(search_pattern, replacement, line), end='')
