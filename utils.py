from os.path import exists
import os
import itertools
from json import load, dump, JSONDecodeError
from secrets import token_hex

import logging

DEFAULT_CONFIG = {
    "SECRET_KEY": token_hex(24),
    "DEBUG": False
}

def ensure_config(filename: str) -> bool:
    if exists(filename):
        try:
            with open(filename) as file:
                _ = load(file)
                logging.info('Config file loaded')
                return True
        except JSONDecodeError:
            logging.error("Config file is malformed")
            return False
    else:
        logging.warning('Config file not found, creating new')
        try:
            with open(filename, "w") as file:
                dump(DEFAULT_CONFIG, file)
                return True
        except Exception as e:
             logging.error("Unable to create config file")
             return False
        
def config_has_key(config: dict, key: str, check_true = False) -> bool:
    """
    Checks whether a key exists in a nested dict

    the key parameter is formatted as "subkey1.subkey2.subkey3"

    if the check_true argument is set to True, the key must exist and also contain a truthy value
    """
    keys = key.split('.')
    subkey = config
    for k in keys:
        subkey = subkey.get(k)
        if not subkey: return False
    if not check_true:
        return True
    else:
        return bool(subkey)

def count_files_rec(dir: str | os.PathLike) -> int:
    """
    Recursively counts the files contained in dir and all its subdirectories
    """
    # Ignore the root and dirs tuples that os.walk returns and empty the generator into a list
    file_list = [file for _, _, file in os.walk(dir)]
    # There's one list for each directory so we have to flatten them
    flat_list = itertools.chain.from_iterable(file_list)
    # itertools.chain gives us a generator again because this language is silly
    # empty it into a list again and return the length
    return len(list(flat_list))
