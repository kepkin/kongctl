import sys
from termcolor import colored


class JsonOutputFormatter(object):
    def __init__(self, output_file=sys.stdout, indent_spacer="  "):
        self._colored = self._dummy_colored
        self.indent_spacer_char = indent_spacer
        self.output_file = output_file

        if self.output_file.isatty():
            self._colored = colored

    def indent_spacer(self, num):
        return self.indent_spacer_char * num

    @staticmethod
    def _dummy_colored(string, *_, **__):
        return string

    def print_obj(self, data, indent=0):
        if isinstance(data, dict):
            self.print_dict(data, indent)
        elif isinstance(data, str):
            self._write('"{}"'.format(data.replace('\n', "\\n")))
        elif isinstance(data, list):
            self.print_list(data, indent)
        elif isinstance(data, tuple):
            self.print_list(data, indent)
        elif isinstance(data, bool):
            self._write('true' if data else 'false')
        else:
            self._write('{}'.format(data))

    def print_list(self, data, indent=0):
        self._write('[')

        not_first = False
        for v in data:
            if not_first:
                self._write(', ')
            not_first = True
            self.print_obj(v, indent)

        self._write(']')

    def print_dict(self, data, indent=0):
        self._write('{\n')
        keys = list(data.keys())
        keys.sort()

        not_first = False
        for k in keys:
            if not_first:
                self._write(',\n')
            not_first = True

            v = data[k]
            self._write(self.indent_spacer(indent + 1))
            self._write('"{}"'.format(k), 'blue')
            self._write(': ')
            self.print_obj(v, indent + 1)

        self._write('\n')
        self._write(self.indent_spacer(indent))
        self._write('}')

    def print_header(self, data):
        self._write(data + '\n', attrs=['bold'])

    def println(self, *data, indent=0):
        self._write(self.indent_spacer(indent))
        self._write(" ".join(data) + '\n')

    def print_pair(self, k, data, indent=0):
        self._write(self.indent_spacer(indent))
        self._write(k, 'blue')
        self._write(': ')
        self._write(data)
        self._write('\n')

    def _write(self, string, *args, **kwargs):
        print(self._colored(string, *args, **kwargs), file=self.output_file, end='')
