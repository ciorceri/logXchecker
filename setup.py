from cx_Freeze import setup, Executable
base = 'Console'
executables = [Executable("logXchecker.py", base=base)]
setup(
    name = "logXchecker",
    version = "June 2017",
    description = 'logXchecker log cross checker',
    executables = executables
)
