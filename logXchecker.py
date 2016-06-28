import argparse


class Parser():
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='log cross checker')
        self.parser.add_argument('-f', '--format', type=str, required=True, help="Log format")
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument('-slc', '--singlelogcheck', action='store_true', default=False)
        group.add_argument('-mlc', '--multilogcheck', action='store_true', default=False)

    def parse(self, commandLine):
        return self.parser.parse_args(commandLine)
