import unittest
from text_analyzer import *
from io import StringIO


class TestTextAnalyzer(unittest.TestCase):
    def test_find_substring(self):
        self.assertEqual(find_substring("Hello, world!", "world"), 7)

    def test_replace_substring(self):
        self.assertEqual(replace_substring("Hello, world!", "world", "Python"), "Hello, Python!")

    def test_split_text(self):
        self.assertEqual(split_text("Hello, world!", ", "), ["Hello", "world!"])

    def test_format_string_f(self):
        self.assertEqual(format_string_f("Alice", 30), "Мене звати Alice і мені 30 років.")

    def test_format_string_method(self):
        self.assertEqual(format_string_method("Bob", 25), "Мене звати Bob і мені 25 років.")

    def test_extract_emails(self):
        self.assertEqual(extract_emails("Contact us at info@example.com or support@test.com"),
                         ["info@example.com", "support@test.com"])

    def test_validate_phone_number(self):
        self.assertTrue(validate_phone_number("+380123456789"))
        self.assertFalse(validate_phone_number("12345"))

    def test_extract_hashtags(self):
        self.assertEqual(extract_hashtags("I love #Python and #Programming"), ["#Python", "#Programming"])

    def test_extract_mentions(self):
        self.assertEqual(extract_mentions("Hello @user1 and @user2"), ["@user1", "@user2"])

    def test_count_words(self):
        self.assertEqual(count_words("This is a test sentence."), 5)

    def test_count_sentences(self):
        self.assertEqual(count_sentences("This is one. This is two! Is this three?"), 3)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTextAnalyzer)
    output = StringIO()
    runner = unittest.TextTestRunner(stream=output, verbosity=2)
    result = runner.run(suite)

    print(output.getvalue())
    print(f"\nУспішних тестів: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Невдалих тестів: {len(result.failures)}")
    print(f"Помилок: {len(result.errors)}")

    if result.failures or result.errors:
        print("\nДетальна інформація про невдалі тести та помилки:")
        for test, error in result.failures + result.errors:
            print(f"\n{test}")
            print(error)