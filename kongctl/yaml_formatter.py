from .json_formatter import JsonOutputFormatter


class YamlOutputFormatter(JsonOutputFormatter):
    first_move = 2

    def print_obj(self, data, indent=0, tab=1):
        if self.first_move == 2:
            self.print_version()
        if isinstance(data, dict):
            self.print_dict(data, indent, tab)
        elif isinstance(data, str):
            self._write('{}'.format(data.replace('\n', "\\n")))
        elif isinstance(data, list):
            self.print_list(data, indent)
        elif isinstance(data, tuple):
            self.print_list(data, indent)
        elif isinstance(data, bool):
            self._write('true' if data else 'false')
        elif data is None:
            self._write('~')
        else:
            self._write('{}'.format(data))

    def print_list(self, data, indent=0, isn=1):
        if len(data) != 0:
            self._write('\n' + self.indent_spacer(indent) + '- ', 'green')
            not_first = False
            for v in data:
                if not_first:
                    self._write('\n' + self.indent_spacer(indent) + '- ', 'green')
                not_first = True
                if isinstance(v, dict):
                    self.print_obj(v, -1, 0)
                else:
                    self.print_obj(v, indent + isn, 0)
        else:
            self._write('[]')

    def print_dict(self, data, indent=0, tab=1):
        keys = list(data.keys())
        keys.sort()
        if tab and not self.first_move:
            self._write('\n')
        tab = 1
        self.first_move = 0
        not_first = False
        for k in keys:
            if not_first:
                self._write('\n')
            not_first = True
            v = data[k]
            self._write(self.indent_spacer(indent))
            self._write('{}'.format(k), 'red')
            self._write(': ')
            if indent < 0:
                indent = 2
            self.print_obj(v, indent + 1, tab)
        self._write(self.indent_spacer(indent))

    def print_version(self):
        self._write("_format_version: \"1.1\"\n")
