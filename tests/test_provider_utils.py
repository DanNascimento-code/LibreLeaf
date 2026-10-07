from libreleaf.providers.utils import contains_isbn, get_path, infer_book_format, nested_strings


def test_provider_utilities() -> None:
    nested = {"one": [{"value": "9780132350884"}], "two": ("x",)}
    assert contains_isbn(nested, "9780132350884")
    assert list(nested_strings(nested)) == ["9780132350884", "x"]
    assert get_path({"a": {"b": 0}}, "a", "b", default=4) == 0
    assert get_path({}, "a", default=4) == 4
    assert infer_book_format("Title (Kindle Edition)") == "ebook"
    assert infer_book_format("Title — Capa dura") == "hardcover"
    assert infer_book_format("Title Paperback") == "paperback"
    assert infer_book_format("Title") == "unknown"
