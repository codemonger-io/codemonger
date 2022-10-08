# -*- coding: utf-8 -*-

"""Common exceptions.
"""

class DataWarehouseException(Exception):
    """Base exception raised when a data warehouse operation fails.
    """
    def __init__(self, message: str):
        """Initializes with a message.
        """
        self.message = message


    def __str__(self) -> str:
        classname = type(self).__name__
        return f'{classname}({self.message})'


    def __repr__(self) -> str:
        classname = type(self).__name__
        return f'{classname}({repr(self.message)})'
