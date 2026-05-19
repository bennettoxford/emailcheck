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


def test_main_prints_matches_and_exits_one(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("some text bob@test.org alice@test.co.uk")

    assert emailcheck.main([str(path)]) == 1
    assert capsys.readouterr().out == "".join(
        [
            "Detected strings which look like email addresses:\n",
            "\n",
            f"{path}: bob@test.org\n",
            f"{path}: alice@test.co.uk\n",
        ]
    )


def test_main_exits_zero_when_there_are_no_matches(tmp_path, capsys):
    path = tmp_path / "content.txt"
    path.write_text("no emails here")

    assert emailcheck.main([str(path)]) == 0
    assert capsys.readouterr().out == ""
