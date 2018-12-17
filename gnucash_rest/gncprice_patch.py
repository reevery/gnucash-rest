'''
Monkey patch for GnuCash Python bindings as the Python class GncPrice does not implement a correct __init__ method by default
'''

import datetime
import gnucash.gnucash_core_c
from gnucash.function_class import ClassFromFunctions
from gnucash import Session, GncPrice, GncNumeric


def create_price(self, book=None, instance=None):
    if instance:
        price_instance = instance
    else:
        price_instance = gnucash.gnucash_core_c.gnc_price_create(book.get_instance())
    ClassFromFunctions.__init__(self, instance=price_instance)


GncPrice.__init__ = create_price