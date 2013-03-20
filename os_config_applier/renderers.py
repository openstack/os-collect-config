import json

from pystache import Renderer


class JsonRenderer(Renderer):
    def __init__(self,
                 file_encoding=None,
                 string_encoding=None,
                 decode_errors=None,
                 search_dirs=None,
                 file_extension=None,
                 escape=None,
                 partials=None,
                 missing_tags=None):
        # json would be html escaped otherwise
        if escape is None:
            escape = lambda u: u
        return super(JsonRenderer, self).__init__(file_encoding,
                                                  string_encoding,
                                                  decode_errors, search_dirs,
                                                  file_extension, escape,
                                                  partials, missing_tags)

    def str_coerce(self, val):
        return json.dumps(val)
