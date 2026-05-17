from typing import List
from cx_Freeze import setup, Executable

base: str = 'Console'
executables: List[Executable] = [Executable("logXchecker.py", base=base)]
setup(
    name="logXchecker",
    version="1.4",
    description='ham radio log cross checker',
    executables=executables,
)
