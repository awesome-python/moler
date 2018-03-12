# -*- coding: utf-8 -*-
"""
Package for implementing different commands based on Moler Command.
"""
from re import search, match

__author__ = 'Grzegorz Latuszek'
__copyright__ = 'Copyright (C) 2018, Nokia'
__email__ = 'grzegorz.latuszek@nokia.com'


class RegexHelper(object):
    instance = None

    def __init__(self):
        self.match = None

    def search(self, pattern, string, flags=0):
        self.match = search(pattern, string, flags)
        return self.match

    def search_compiled(self, compiled, string):
        self.match = compiled.search(string)
        return self.match

    def match(self, pattern, string, flags=0):
        self.match = match(pattern, string, flags)
        return self.match

    def match_compiled(self, compiled, string):
        self.match = compiled.match(string)
        return self.match

    def get_match(self):
        return self.match

    def group(self, number):
        return self.match.group(number)

    @staticmethod
    def get_regex_helper():
        if RegexHelper.instance is None:
            RegexHelper.instance = RegexHelper()
        return RegexHelper.instance