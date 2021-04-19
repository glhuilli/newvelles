import unittest

from newvelles.utils.text import process_content
from newvelles.utils.text import remove_subsets


TEST_CASES = {
    'Limbic is a package.': ['limbic', 'package'],
    'a random number 111': ['random', 'number'],
    "something I didn't expected to test with l'huillier.": ['didnt', 'expected', 'test', 'lhuillier'],
    "l'huillier is a last name a will not change.": ["l'huillier", "change"],
    "didn't will be removed (stopword).": ["removed", 'stopword'],
    '': ['']
}
TERMS_MAPPING = {'dog': 'cat'}
TEST_CASES_TERMS_MAPPING = {'this is a dog': 'this is a cat'}


class TestUtilText(unittest.TestCase):
    def test_process_content(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test)
            self.assertEqual(output, expected_output)

    def test_process_content_with_terms_mapping(self):
        for input_test, expected_output in TEST_CASES.items():
            output = process_content(input_test, terms_mapping=TERMS_MAPPING)
            self.assertEqual(output, expected_output)

    def test_remove_subsets(self):
        sets = [[0, 1, 3], [0, 1], [2], [0, 3], [4]]
        output = {(0, 1, 3), (2,), (4,)}
        self.assertEquals(remove_subsets(sets), output)
