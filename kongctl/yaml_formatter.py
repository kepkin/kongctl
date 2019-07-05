from .json_formatter import JsonOutputFormatter


class YamlOutputFormatter(JsonOutputFormatter):
    def print_obj(self, data, indent=0):
        self._print_obj(data, indent)
        self._write('\n')

    def _print_obj(self, data, indent=0, from_type=None):
        if isinstance(data, dict):
            self.print_dict(data, indent, from_type=from_type)
        elif isinstance(data, str):
            self.print_str(data, indent)
        elif isinstance(data, list):
            self.print_list(data, indent, from_type=from_type)
        elif isinstance(data, tuple):
            self.print_list(data, indent)
        elif isinstance(data, bool):
            self._write('true' if data else 'false')
        elif data is None:
            self._write('~')
        else:
            self._write('{}'.format(data))

    def print_str(self, data, indent=0):
        if data.count('\n') > 1:
            data = self.indent_spacer_char * indent + data.replace('\n', '\n' + self.indent_spacer_char * indent)
            if data[-1] != '\n':
                data = '|-\n' + data
            elif data[-2] == '\n':
                data = '|+\n' + data
            else:
                data = '|\n' + data
        else:
            data = data.replace('\n', '\\n')
        self._write(data)

    def print_list(self, data, indent=0, from_type=None):
        if len(data) == 0:
            self._write('[]')
            return

        not_first = False

        for v in data:
            if not_first or from_type is dict:
                self._write('\n')
            not_first = True

            self._write(self.indent_spacer(indent) + '- ', 'green')
            self._print_obj(v, indent + 1, from_type=list)

    def print_dict(self, data, indent=0, from_type=None):
        if len(data) == 0:
            self._write('{}')
            return

        keys = list(data.keys())
        not_first = False
        for k in keys:
            if not_first or from_type is dict:
                self._write('\n')
                self._write(self.indent_spacer(indent))
            not_first = True
            v = data[k]

            self._write('{}'.format(k), 'red')
            self._write(': ')
            self._print_obj(v, indent + 1, from_type=dict)
