# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

import pystache


class JsonRenderer(pystache.Renderer):
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
