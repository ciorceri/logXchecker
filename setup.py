from typing import List
from cx_Freeze import setup, Executable

base: str = 'Console'
executables: List[Executable] = [Executable("logXchecker.py", base=base)]
setup(
    name="logXchecker",
    version="2.0",
    description='ham radio log cross checker',
    executables=executables,
)
