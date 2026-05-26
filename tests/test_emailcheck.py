import pickle

import emailcheck


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


def test_find_emails_ignores_example_domain():
    text = "dave@example.com"
    assert list(emailcheck.find_emails(text.encode())) == []


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
        ]
    )


def test_main_exits_zero_when_there_are_no_matches(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("no emails here")

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_uses_ignore_file_from_current_working_directory(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "content.txt"
    path.write_text("some text Bob@test.org Alice@test.co.uk")
    tmp_path.joinpath(".emailcheck_ignore").write_text(
        "alice@TEST.CO.UK bob@test.org\n"
    )
    monkeypatch.chdir(tmp_path)

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""
