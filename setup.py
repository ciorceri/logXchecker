from cx_Freeze import setup, Executable
base = 'Console'
executables = [Executable("logXchecker.py", base=base)]
setup(
    name = "logXchecker",
    version = "1.0",
    description = 'ham radio log cross checker',
    executables = executables
)
