"""Unit tests for :mod:`darker.git`"""

# pylint: disable=redefined-outer-name

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from darker.git import (
    EditedLinenumsDiffer,
    RevisionRange,
    git_get_content_at_revision,
    git_get_modified_files,
    should_reformat_file,
)
from darker.tests.conftest import GitRepoFixture
from darker.tests.helpers import raises_if_exception
from darker.utils import TextDocument


@pytest.mark.parametrize(
    "revision, expect",
    [
        (":WORKTREE:", ("new content",)),
        ("HEAD", ("modified content",)),
        ("HEAD^", ("original content",)),
        ("HEAD~2", ()),
    ],
)
def test_git_get_content_at_revision(git_repo, revision, expect):
    """darker.git.git_get_content_at_revision()"""
    git_repo.add({"my.txt": "original content"}, commit="Initial commit")
    paths = git_repo.add({"my.txt": "modified content"}, commit="Initial commit")
    paths["my.txt"].write("new content")

    original = git_get_content_at_revision(
        Path("my.txt"), revision, cwd=Path(git_repo.root)
    )

    assert original.lines == expect


@pytest.mark.parametrize(
    "revision, expect",
    [
        ("HEAD^", "git show HEAD^:./my.txt"),
        ("master", "git show master:./my.txt"),
    ],
)
def test_git_get_content_at_revision_git_calls(revision, expect):
    with patch("darker.git.check_output") as check_output:
        check_output.return_value = "dummy output"

        git_get_content_at_revision(Path("my.txt"), revision, Path("cwd"))

        check_output.assert_called_once_with(
            expect.split(), cwd="cwd", encoding="utf-8"
        )


@pytest.mark.parametrize(
    'path, create, expect',
    [
        ('.', False, False),
        ('main', True, False),
        ('main.c', True, False),
        ('main.py', True, True),
        ('main.py', False, False),
        ('main.pyx', True, False),
        ('main.pyi', True, False),
        ('main.pyc', True, False),
        ('main.pyo', True, False),
        ('main.js', True, False),
    ],
)
def test_should_reformat_file(tmpdir, path, create, expect):
    if create:
        (tmpdir / path).ensure()

    result = should_reformat_file(Path(tmpdir / path))

    assert result == expect


@pytest.mark.parametrize(
    'modify_paths, paths, expect',
    [
        ({}, ['a.py'], []),
        ({}, [], []),
        ({'a.py': 'new'}, [], ['a.py']),
        ({'a.py': 'new'}, ['b.py'], []),
        ({'a.py': 'new'}, ['a.py', 'b.py'], ['a.py']),
        ({'c/d.py': 'new'}, ['c/d.py', 'd/f/g.py'], ['c/d.py']),
        ({'c/e.js': 'new'}, ['c/e.js'], []),
        ({'a.py': 'original'}, ['a.py'], []),
        ({'a.py': None}, ['a.py'], []),
        ({"h.py": "untracked"}, ["h.py"], ["h.py"]),
        ({}, ["h.py"], []),
    ],
)
def test_git_get_modified_files(git_repo, modify_paths, paths, expect):
    """Tests for `darker.git.git_get_modified_files()`"""
    root = Path(git_repo.root)
    git_repo.add(
        {
            'a.py': 'original',
            'b.py': 'original',
            'c/d.py': 'original',
            'c/e.js': 'original',
            'd/f/g.py': 'original',
        },
        commit="Initial commit",
    )
    for path, content in modify_paths.items():
        absolute_path = git_repo.root / path
        if content is None:
            absolute_path.remove()
        else:
            absolute_path.write(content, ensure=True)

    result = git_get_modified_files(
        {root / p for p in paths}, RevisionRange("HEAD"), cwd=root
    )

    assert {str(p) for p in result} == set(expect)


@pytest.fixture(scope="module")
def branched_repo(tmpdir_factory):
    """Create an example Git repository with a master branch and a feature branch

    The history created is::

        . worktree
        . index
        * branch
        | * master
        |/
        * Initial commit

    """
    tmpdir = tmpdir_factory.mktemp("branched_repo")
    git_repo = GitRepoFixture.create_repository(tmpdir)
    git_repo.add(
        {
            "del_master.py": "original",
            "del_branch.py": "original",
            "del_index.py": "original",
            "del_worktree.py": "original",
            "mod_master.py": "original",
            "mod_branch.py": "original",
            "mod_both.py": "original",
            "mod_same.py": "original",
            "keep.py": "original",
        },
        commit="Initial commit",
    )
    branch_point = git_repo.get_hash()
    git_repo.add(
        {
            "del_master.py": None,
            "add_master.py": "master",
            "mod_master.py": "master",
            "mod_both.py": "master",
            "mod_same.py": "same",
        },
        commit="master",
    )
    git_repo.create_branch("branch", branch_point)
    git_repo.add(
        {
            "del_branch.py": None,
            "mod_branch.py": "branch",
            "mod_both.py": "branch",
            "mod_same.py": "same",
        },
        commit="branch",
    )
    git_repo.add(
        {"del_index.py": None, "add_index.py": "index", "mod_index.py": "index"}
    )
    (git_repo.root / "del_worktree.py").remove()
    (git_repo.root / "add_worktree.py").write_binary(b"worktree")
    (git_repo.root / "mod_worktree.py").write_binary(b"worktree")
    return git_repo


@pytest.mark.parametrize(
    "_description, revrange, expect",
    [
        (
            "from latest commit in branch to worktree and index",
            "HEAD",
            {"add_index.py", "add_worktree.py", "mod_index.py", "mod_worktree.py"},
        ),
        (
            "from initial commit to worktree and index on branch (implicit)",
            "master",
            {
                "mod_both.py",
                "mod_same.py",
                "mod_branch.py",
                "add_index.py",
                "mod_index.py",
                "add_worktree.py",
                "mod_worktree.py",
            },
        ),
        (
            "from initial commit to worktree and index on branch",
            "master...",
            {
                "mod_both.py",
                "mod_same.py",
                "mod_branch.py",
                "add_index.py",
                "mod_index.py",
                "add_worktree.py",
                "mod_worktree.py",
            },
        ),
        (
            "from master to worktree and index on branch",
            "master..",
            {
                "del_master.py",
                "mod_master.py",
                "mod_both.py",
                "mod_branch.py",
                "add_index.py",
                "mod_index.py",
                "add_worktree.py",
                "mod_worktree.py",
            },
        ),
        (
            "from master to last commit on branch, excluding worktree and index",
            "master..HEAD",
            {
                "del_master.py",
                "mod_master.py",
                "mod_both.py",
                "mod_branch.py",
            },
        ),
        (
            "from master to branch, excluding worktree and index",
            "master..branch",
            {
                "del_master.py",
                "mod_master.py",
                "mod_both.py",
                "mod_branch.py",
            },
        ),
        (
            "from initial commit to last commit on branch,"
            " excluding worktree and index",
            "master...HEAD",
            {"mod_both.py", "mod_same.py", "mod_branch.py"},
        ),
        (
            "from initial commit to previous commit on branch",
            "master...branch",
            {"mod_both.py", "mod_same.py", "mod_branch.py"},
        ),
    ],
)
def test_git_get_modified_files_revision_range(
    _description, branched_repo, revrange, expect
):
    """Test for :func:`darker.git.git_get_modified_files` with a revision range"""
    result = git_get_modified_files(
        [Path(branched_repo.root)],
        RevisionRange.parse(revrange),
        Path(branched_repo.root),
    )

    assert {path.name for path in result} == expect


@pytest.mark.parametrize(
    "environ, expect_rev1, expect_rev2, expect_use_common_ancestor",
    [
        ({}, "HEAD", ":WORKTREE:", False),
        ({"PRE_COMMIT_FROM_REF": "old"}, "HEAD", ":WORKTREE:", False),
        ({"PRE_COMMIT_TO_REF": "new"}, "HEAD", ":WORKTREE:", False),
        (
            {"PRE_COMMIT_FROM_REF": "old", "PRE_COMMIT_TO_REF": "new"},
            "old",
            "new",
            True,
        ),
    ],
)
def test_revisionrange_parse_pre_commit(
    environ, expect_rev1, expect_rev2, expect_use_common_ancestor
):
    """RevisionRange.parse(':PRE-COMMIT:') gets the range from environment variables"""
    with patch.dict(os.environ, environ):

        result = RevisionRange.parse(":PRE-COMMIT:")

        assert result.rev1 == expect_rev1
        assert result.rev2 == expect_rev2
        assert result.use_common_ancestor == expect_use_common_ancestor


edited_linenums_differ_cases = pytest.mark.parametrize(
    "context_lines, expect",
    [
        (0, [3, 7]),
        (1, [2, 3, 4, 6, 7, 8]),
        (2, [1, 2, 3, 4, 5, 6, 7, 8]),
        (3, [1, 2, 3, 4, 5, 6, 7, 8]),
    ],
)


@edited_linenums_differ_cases
def test_edited_linenums_differ_revision_vs_worktree(git_repo, context_lines, expect):
    """Tests for EditedLinenumsDiffer.revision_vs_worktree()"""
    paths = git_repo.add({"a.py": "1\n2\n3\n4\n5\n6\n7\n8\n"}, commit="Initial commit")
    paths["a.py"].write("1\n2\nthree\n4\n5\n6\nseven\n8\n")
    differ = EditedLinenumsDiffer(Path(git_repo.root), RevisionRange("HEAD"))

    result = differ.compare_revisions(Path("a.py"), context_lines)

    assert result == expect


@edited_linenums_differ_cases
def test_edited_linenums_differ_revision_vs_lines(git_repo, context_lines, expect):
    """Tests for EditedLinenumsDiffer.revision_vs_lines()"""
    git_repo.add({'a.py': '1\n2\n3\n4\n5\n6\n7\n8\n'}, commit='Initial commit')
    content = TextDocument.from_lines(["1", "2", "three", "4", "5", "6", "seven", "8"])
    differ = EditedLinenumsDiffer(git_repo.root, RevisionRange("HEAD"))

    result = differ.revision_vs_lines(Path("a.py"), content, context_lines)

    assert result == expect
