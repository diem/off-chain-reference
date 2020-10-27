# Copyright (c) The Libra Core Contributors
# SPDX-License-Identifier: Apache-2.0


class Database:
    """ The interface that underlying database should implement """

    def get(self, prefix, key):
        """ Given a prefix and key, return the value in db """
        return NotImplementedError()  # pragma: no cover

    def try_get(self, prefix, key):
        """
        Given a prefix and key, return the value in db if it exists, otherwise
        return None
        """
        return NotImplementedError()  # pragma: no cover

    def put(self, prefix, key, val):
        """ Store the prefix/key - value to db"""
        return NotImplementedError()  # pragma: no cover

    def delete(self, prefix, key):
        """ Remove the prefix/key from db if it exists """
        return NotImplementedError()  # pragma: no cover

    def isin(self, prefix, key):
        """ Return whether the given prefix/key is in the db """
        return NotImplementedError()  # pragma: no cover

    def getkeys(self, prefix):
        """ Return the keys in db associated with the given prefix """
        return NotImplementedError()  # pragma: no cover

    def count(self, prefix):
        """ Return the number of rows in db with thte given prefix """
        return NotImplementedError()  # pragma: no cover
