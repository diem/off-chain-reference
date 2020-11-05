# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0
from ..database import Database


def make_key(prefix, key):
    return prefix + "@@" + key


class SampleDB(Database):
    def __init__(self):
        self.data = {}

    def get(self, prefix, key):
        return self.data[make_key(prefix, key)]

    def try_get(self, prefix, key):
        try:
            return self.data[make_key(prefix, key)]
        except KeyError:
            return None

    def put(self, prefix, key, val):
        self.data[make_key(prefix, key)] = val

    def delete(self, prefix, key):
        del self.data[make_key(prefix, key)]

    def isin(self, prefix, key):
        return make_key(prefix, key) in self.data

    def getkeys(self, prefix):
        keys = []
        for k, v in self.data.items():
            if k.startswith(prefix+"@@"):
                keys.append(k[len(prefix+"@@"):])
        return keys

    def count(self, prefix):
        return len(self.getkeys(prefix))
