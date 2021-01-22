"""Unit tests for :mod:`darker.utils`"""

import os
from pathlib import Path
from textwrap import dedent

import pytest

from darker.utils import (
    TextDocument,
    debug_dump,
    get_common_root,
    get_path_ancestry,
    joinlines,
)


def test_debug_dump(capsys):
    debug_dump(
        [(1, ("black",), ("chunks",))],
        TextDocument.from_str("old content"),
        TextDocument.from_str("new content"),
        [2, 3],
    )
    assert capsys.readouterr().out == (
        dedent(
            """\
            --------------------------------------------------------------------------------
             -   1 black
             +     chunks
            --------------------------------------------------------------------------------
            """
        )
    )


def test_joinlines():
    result = joinlines(("a", "b", "c"))
    assert result == "a\nb\nc\n"


def test_get_common_root(tmpdir):
    tmpdir = Path(tmpdir)
    path1 = tmpdir / "a" / "b" / "c" / "d"
    path2 = tmpdir / "a" / "e" / ".." / "b" / "f" / "g"
    path3 = tmpdir / "a" / "h" / ".." / "b" / "i"
    result = get_common_root([path1, path2, path3])
    assert result == tmpdir / "a" / "b"


def test_get_common_root_of_directory(tmpdir):
    tmpdir = Path(tmpdir)
    result = get_common_root([tmpdir])
    assert result == tmpdir


def test_get_path_ancestry_for_directory(tmpdir):
    tmpdir = Path(tmpdir)
    result = list(get_path_ancestry(tmpdir))
    assert result[-1] == tmpdir
    assert result[-2] == tmpdir.parent


def test_get_path_ancestry_for_file(tmpdir):
    tmpdir = Path(tmpdir)
    dummy = tmpdir / "dummy"
    dummy.write_text("dummy")
    result = list(get_path_ancestry(dummy))
    assert result[-1] == tmpdir
    assert result[-2] == tmpdir.parent


@pytest.mark.kwparametrize(
    dict(doc1=TextDocument(lines=["foo"]), doc2=TextDocument(lines=[]), expect=False),
    dict(doc1=TextDocument(lines=[]), doc2=TextDocument(lines=["foo"]), expect=False),
    dict(
        doc1=TextDocument(lines=["foo"]), doc2=TextDocument(lines=["bar"]), expect=False
    ),
    dict(
        doc1=TextDocument(lines=["line1", "line2"]),
        doc2=TextDocument(lines=["line1", "line2"]),
        expect=True,
    ),
    dict(doc1=TextDocument(lines=["foo"]), doc2=TextDocument(""), expect=False),
    dict(doc1=TextDocument(lines=[]), doc2=TextDocument("foo\n"), expect=False),
    dict(doc1=TextDocument(lines=["foo"]), doc2=TextDocument("bar\n"), expect=False),
    dict(
        doc1=TextDocument(lines=["line1", "line2"]),
        doc2=TextDocument("line1\nline2\n"),
        expect=True,
    ),
    dict(doc1=TextDocument("foo\n"), doc2=TextDocument(lines=[]), expect=False),
    dict(doc1=TextDocument(""), doc2=TextDocument(lines=["foo"]), expect=False),
    dict(doc1=TextDocument("foo\n"), doc2=TextDocument(lines=["bar"]), expect=False),
    dict(
        doc1=TextDocument("line1\nline2\n"),
        doc2=TextDocument(lines=["line1", "line2"]),
        expect=True,
    ),
    dict(doc1=TextDocument("foo\n"), doc2=TextDocument(""), expect=False),
    dict(doc1=TextDocument(""), doc2=TextDocument("foo\n"), expect=False),
    dict(doc1=TextDocument("foo\n"), doc2=TextDocument("bar\n"), expect=False),
    dict(
        doc1=TextDocument("line1\nline2\n"),
        doc2=TextDocument("line1\nline2\n"),
        expect=True,
    ),
    dict(doc1=TextDocument("foo"), doc2="line1\nline2\n", expect=NotImplemented),
)
def test_textdocument_eq(doc1, doc2, expect):
    """TextDocument.__eq__()"""
    result = doc1.__eq__(doc2)

    assert result == expect


@pytest.mark.kwparametrize(
    dict(document=TextDocument(""), expect="TextDocument([0 lines])"),
    dict(document=TextDocument(lines=[]), expect="TextDocument([0 lines])"),
    dict(document=TextDocument("One line\n"), expect="TextDocument([1 lines])"),
    dict(document=TextDocument(lines=["One line"]), expect="TextDocument([1 lines])"),
    dict(document=TextDocument("Two\nlines\n"), expect="TextDocument([2 lines])"),
    dict(
        document=TextDocument(lines=["Two", "lines"]), expect="TextDocument([2 lines])"
    ),
)
def test_textdocument_repr(document, expect):
    """TextDocument.__repr__()"""
    result = document.__repr__()

    assert result == expect


@pytest.mark.kwparametrize(
    dict(document=TextDocument(), expect=""),
    dict(document=TextDocument(mtime=""), expect=""),
    dict(document=TextDocument(mtime="dummy mtime"), expect="dummy mtime"),
)
def test_textdocument_mtime(document, expect):
    """TextDocument.mtime"""
    assert document.mtime == expect


def test_textdocument_from_file(tmp_path):
    """TextDocument.from_file()"""
    dummy_txt = tmp_path / "dummy.txt"
    dummy_txt.write_text("dummy\ncontent\n")
    os.utime(dummy_txt, (1_000_000_000, 1_000_000_000))

    document = TextDocument.from_file(dummy_txt)

    assert document.string == "dummy\ncontent\n"
    assert document.lines == ("dummy", "content")
    assert document.mtime == "2001-09-09 01:46:40.000000 +0000"
