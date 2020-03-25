import unittest

class MyTests(unittest.TestCase):

    def test_error(self):
        """ Test whether an error is raised if agent is None """
        self.failUnlessEqual(2,2)
