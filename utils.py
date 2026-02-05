from os.path import exists
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