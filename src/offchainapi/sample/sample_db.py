# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0

def make_key(ns, key):
    return ns + "@@" + key


class SampleDB:
    def __init__(self):
        self.data = {}

    def get(self, ns, key):
        return self.data[make_key(ns, key)]

    def try_get(self, ns, key):
        """
        Returns value if key exists in storage, otherwise returns None
        """
        try:
            return self.data[make_key(ns, key)]
        except KeyError:
            return None

    def put(self, ns, key, val):
        self.data[make_key(ns, key)] = val

    def delete(self, ns, key):
        del self.data[make_key(ns, key)]

    def isin(self, ns, key):
        return make_key(ns, key) in self.data

    def getkeys(self, ns):
        keys = []
        for k, v in self.data.items():
            if k.startswith(ns+"@@"):
                keys.append(k[len(ns+"@@"):])
        return keys

    def count(self, ns):
        return len(self.getkeys(ns))
