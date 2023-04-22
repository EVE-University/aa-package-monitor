import unittest

from .stubs import PackageMetadataStub


class TestPackageMetadata(unittest.TestCase):
    def test_single(self):
        # given
        d = PackageMetadataStub()
        # when
        d["one"] = 1
        # then
        self.assertEqual(d["one"], 1)

    def test_many(self):
        # given
        d = PackageMetadataStub()
        # when
        d["one"] = 1
        d["one"] = 2
        # then
        self.assertEqual(d["one"], 1)

    def test_should_return_multi_keys(self):
        # given
        d = PackageMetadataStub()
        # when
        d["one"] = 1
        d["one"] = 2
        d["two"] = 3
        # then
        self.assertEqual(d.keys(), ["one", "one", "two"])

    def test_should_return_multi_items(self):
        # given
        d = PackageMetadataStub()
        # when
        d["one"] = 1
        d["one"] = 2
        d["two"] = 3
        # then
        self.assertEqual(d.items(), [("one", 1), ("one", 2), ("two", 3)])

    def test_should_return_multi_values(self):
        # given
        d = PackageMetadataStub()
        # when
        d["one"] = 1
        d["one"] = 2
        d["two"] = 3
        # then
        self.assertEqual(d.values(), [1, 2, 3])

    def test_should_init_with_dict(self):
        # given
        d = PackageMetadataStub({"one": 1, "two": 2})
        # when
        d["two"] = 3
        # then
        self.assertEqual(d.items(), [("one", 1), ("two", 2), ("two", 3)])

    def test_should_return_first_value(self):
        # given
        d = PackageMetadataStub()
        d["one"] = 1
        d["one"] = 2
        # when/then
        self.assertEqual(d.get("one"), 1)

    def test_should_return_None_if_not_found(self):
        # given
        d = PackageMetadataStub()
        # when/then
        self.assertIsNone(d.get("xxx"))

    def test_should_all_values(self):
        # given
        d = PackageMetadataStub()
        d["one"] = 1
        d["one"] = 2
        # when/then
        self.assertEqual(d.get_all("one"), [1, 2])

    def test_should_return_None_if_not_found_2(self):
        # given
        d = PackageMetadataStub()
        # when/then
        self.assertIsNone(d.get_all("xxx"))
