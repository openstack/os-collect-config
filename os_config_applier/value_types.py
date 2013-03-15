import re
from config_exception import ConfigException

TYPES = {
    "int": "^[0-9]+$",
    "default": "^[A-Za-z0-9]+$",
    "raw": "."
}


def ensure_type(string_value, type_name='default'):
    if type_name not in TYPES:
        raise ValueError(
            "requested validation of unknown type: %s" % type_name)
    if not re.match(TYPES[type_name], string_value):
        raise ConfigException("cannot interpret value '%s' as type %s" % (
            string_value, type_name))
    return string_value
