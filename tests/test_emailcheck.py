import pickle
import subprocess
import unittest.mock

import pytest

import emailcheck


def git(*args, cwd):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def test_find_emails():
    text = """
        alice@test.org
        BOB@TEST.ORG
        "alice@test.org"
        {bob@test.org}
        alice@subdomain.test.org
        name123.other_name+label@my-site.com
    """
    assert list(emailcheck.find_emails(text.encode())) == [
        "alice@test.org",
        "BOB@TEST.ORG",
        "alice@test.org",
        "bob@test.org",
        "alice@subdomain.test.org",
        "name123.other_name+label@my-site.com",
    ]


def test_find_emails_still_matches_long_addresses():
    text = """
        some_long_address_foobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobar@test.com
    """
    assert list(emailcheck.find_emails(text.encode())) == [
        "obarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobarfoobar@test.com"
    ]


def test_find_emails_ignores_other_uses_of_at_mark():
    text = """
    @my_decorator
    def some_function():
        matrix_c = matrix_a @ matrix_b
        matrix_d = matrix_c@matrix_b
        notify_slack_user("@someone", f"Your matrix is ready: {matrix_c}")

    <a href="//cdn.jsdelivr.net/npm/bootstrap-select@1.13.9">
    """
    assert list(emailcheck.find_emails(text.encode())) == []


def test_find_emails_handles_non_utf8_encodings():
    text = "caf\xe9 bob@test.org \xa310"
    content = text.encode("latin-1")

    assert list(emailcheck.find_emails(content)) == ["bob@test.org"]


def test_find_emails_ignores_binary_files():
    content = pickle.dumps({1: "abc@def.gh"})
    assert list(emailcheck.find_emails(content)) == []


def test_find_emails_ignores_specified_addresses():
    text = "bob@test.org Alice@Test.Org carol@test.org"

    assert list(emailcheck.find_emails(text.encode(), {"alice@test.org"})) == [
        "bob@test.org",
        "carol@test.org",
    ]


def test_find_emails_ignores_specified_domains():
    text = "bob@test.com Alice@TEST.com carol@test.org"

    assert list(emailcheck.find_emails(text.encode(), {"@test.com"})) == [
        "carol@test.org",
    ]


def test_read_ignored_emails_returns_empty_set_when_file_does_not_exist(tmp_path):
    assert emailcheck.read_ignored_emails(tmp_path / ".emailcheck_ignore") == set()


def test_read_ignored_emails_ignores_comments_and_whitespace(tmp_path):
    path = tmp_path / ".emailcheck_ignore"
    path.write_text(
        """
        # Ignore personal addresses.
        alice@test.org
          bob@test.org  # needed for fixtures

        CAROL@Test.Org dan@test.org
        """
    )

    assert emailcheck.read_ignored_emails(path) == {
        "alice@test.org",
        "bob@test.org",
        "carol@test.org",
        "dan@test.org",
    }


def test_main_pre_push_check_finds_email_removed_before_push(
    tmp_path, monkeypatch, capsys
):
    git("init", cwd=tmp_path)
    git("config", "user.name", "Test User", cwd=tmp_path)
    git("config", "user.email", "test@example.com", cwd=tmp_path)

    contacts = tmp_path / "contacts.txt"
    contacts.write_text("No email addresses yet\n")
    git("add", "contacts.txt", cwd=tmp_path)
    git("commit", "-m", "Initial commit", cwd=tmp_path)
    from_ref = git("rev-parse", "HEAD", cwd=tmp_path).stdout.strip()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", from_ref)
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "HEAD")
    assert emailcheck.main([]) == 0
    assert capsys.readouterr().out == ""

    contacts.write_text("alice@personal.test\nbob@personal.test\n")
    git("commit", "-am", "Add contact", cwd=tmp_path)
    email_commit = git("rev-parse", "HEAD", cwd=tmp_path).stdout.strip()

    contacts.write_text("No email addresses here\n")
    git("commit", "-am", "Remove contact", cwd=tmp_path)

    assert emailcheck.main([]) == 1

    output = capsys.readouterr().out
    assert f"{email_commit[:8]} contacts.txt: alice@personal.test" in output
    assert f"{email_commit[:8]} contacts.txt: bob@personal.test" in output


def test_main_requires_filenames_without_pre_push_env_vars(capsys, monkeypatch):
    monkeypatch.delenv("PRE_COMMIT_FROM_REF", raising=False)
    monkeypatch.delenv("PRE_COMMIT_TO_REF", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        emailcheck.main([])

    assert exc_info.value.code == 2
    assert "the following arguments are required: filenames" in capsys.readouterr().err


def test_main_requires_both_pre_push_env_vars(capsys, monkeypatch):
    monkeypatch.delenv("PRE_COMMIT_FROM_REF", raising=False)
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "HEAD")
    with pytest.raises(SystemExit) as exc_info:
        emailcheck.main([])

    assert exc_info.value.code == 2
    assert (
        "PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF environment variables must both "
        "be set if either is"
    ) in capsys.readouterr().err


def test_main_pre_push_ignores_filenames_and_uses_pre_commit_refs(
    tmp_path, monkeypatch, capsys
):
    mocked = unittest.mock.Mock(
        spec=emailcheck.get_additions_between_git_refs, return_value=()
    )

    monkeypatch.setattr(emailcheck, "get_additions_between_git_refs", mocked)
    monkeypatch.setenv("PRE_COMMIT_FROM_REF", "origin/main")
    monkeypatch.setenv("PRE_COMMIT_TO_REF", "HEAD")

    assert emailcheck.main(["does-not-exist.txt"]) == 0
    mocked.assert_called_once_with("origin/main", "HEAD")
    assert capsys.readouterr().out == ""


def test_main_prints_matches_and_exits_one(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("some text Bob@test.org alice@TEST.co.uk")

    assert emailcheck.main([str(path)]) == 1
    assert capsys.readouterr().out == "".join(
        [
            "Detected strings which look like email addresses:\n",
            "\n",
            f"{path}: Bob@test.org\n",
            f"{path}: alice@TEST.co.uk\n",
            "\n",
            "If these are not Personally Identifiable Information and legitimately\n",
            "belong in this repo then you can add them to an `.emailcheck_ignore` file\n",
            "in the project root directory.\n",
            "\n",
            "To ignore all addresses from a particular domain use: @example-domain.com\n",
        ]
    )


def test_main_exits_zero_when_there_are_no_matches(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("no emails here")

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_ignores_example_domain_by_default(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("dave@example.com")

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_uses_ignore_file_from_current_working_directory(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "content.txt"
    path.write_text("some text Bob@test.org Alice@test.co.uk carol@example.com")
    tmp_path.joinpath(".emailcheck_ignore").write_text(
        "alice@TEST.CO.UK bob@test.org\n"
    )
    monkeypatch.chdir(tmp_path)

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""
