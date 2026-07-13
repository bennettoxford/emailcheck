import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_pre_commit_hook_rejects_commits_appropriately(tmp_path):
    repo, env = create_test_repo(tmp_path)

    repo.joinpath("notes.txt").write_text("No email addresses here")
    run(["git", "add", "notes.txt"], repo, env)
    clean_commit = run(
        ["git", "commit", "-m", "Add clean file"],
        repo,
        env,
    )

    assert clean_commit.returncode == 0

    repo.joinpath("contacts.txt").write_text("bob@test.org")
    run(["git", "add", "contacts.txt"], repo, env)
    blocked_commit = run(
        ["git", "commit", "-m", "Add file with email address"],
        repo,
        env,
        check=False,
    )
    output = blocked_commit.stdout + blocked_commit.stderr

    assert blocked_commit.returncode != 0
    assert "Detected strings which look like email addresses" in output
    assert "bob@test.org" in output

    repo.joinpath(".emailcheck_ignore").write_text(
        """
        # This address is intentionally present in the test fixture.
        bob@test.org
        """
    )
    run(["git", "add", ".emailcheck_ignore"], repo, env)
    ignored_commit = run(
        ["git", "commit", "-m", "Add ignored email address"],
        repo,
        env,
    )

    assert ignored_commit.returncode == 0

    committed_files = run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        repo,
        env,
    ).stdout.splitlines()

    assert ".emailcheck_ignore" in committed_files
    assert "contacts.txt" in committed_files


def test_pre_push_hook_rejects_email_removed_before_push(tmp_path):
    repo, env = create_test_repo(tmp_path)

    remote = tmp_path / "remote.git"
    run(["git", "init", "--bare", remote], tmp_path, env)
    run(["git", "remote", "add", "origin", remote], repo, env)
    run(["git", "push", "--no-verify", "origin", "HEAD:main"], repo, env)

    contacts = repo / "contacts.txt"
    contacts.write_text("alice@personal.test\n")
    run(["git", "add", "contacts.txt"], repo, env)
    run(["git", "commit", "--no-verify", "-m", "Add contact"], repo, env)

    contacts.write_text("No email addresses here\n")
    run(["git", "commit", "--no-verify", "-am", "Remove contact"], repo, env)

    blocked_push = run(["git", "push", "origin", "HEAD:main"], repo, env, check=False)
    output = blocked_push.stdout + blocked_push.stderr

    assert blocked_push.returncode != 0
    assert "Detected strings which look like email addresses" in output
    assert "contacts.txt: alice@personal.test" in output


def create_test_repo(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(home),
        "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home"),
    }

    hook_repo = tmp_path / "hook-repo"
    hook_rev = create_hook_repo(hook_repo, env)

    test_repo = tmp_path / "repo"
    test_repo.mkdir()
    run(["git", "init"], test_repo, env)
    configure_git(test_repo, env)

    test_repo.joinpath(".pre-commit-config.yaml").write_text(
        textwrap.dedent(
            f"""\
            default_language_version:
              python: {yaml_quote(sys.executable)}

            default_install_hook_types:
              - pre-commit
              - pre-push

            repos:
              - repo: {yaml_quote(str(hook_repo))}
                rev: {yaml_quote(hook_rev)}
                hooks:
                  - id: emailcheck
            """
        )
    )
    run(
        [sys.executable, "-m", "pre_commit", "install", "--install-hooks"],
        test_repo,
        env,
    )

    run(["git", "add", ".pre-commit-config.yaml"], test_repo, env)
    run(["git", "commit", "-m", "Configure pre-commit"], test_repo, env)
    return test_repo, env


def create_hook_repo(path, env):
    # pre-commit requires a real commit ref for the hook under test, so in order to test
    # our uncommitted code we copy it into a temporary repo. This looks a bit
    # heavyweight, but it's exactly what the offical "pre-commit try-repo" command does,
    # except that our implementation is much simpler and less general.
    #
    # https://github.com/pre-commit/pre-commit/blob/edad96821ac4/pre_commit/commands/try_repo.py#L28
    path.mkdir()
    for filename in (
        ".pre-commit-hooks.yaml",
        "emailcheck.py",
        "LICENSE",
        "pyproject.toml",
        "README.md",
    ):
        shutil.copy2(ROOT / filename, path / filename)

    run(["git", "init"], path, env)
    configure_git(path, env)
    run(["git", "add", "."], path, env)
    run(["git", "commit", "-m", "Create hook repo"], path, env)
    return run(["git", "rev-parse", "HEAD"], path, env).stdout.strip()


def configure_git(repo, env):
    run(["git", "config", "user.name", "Test User"], repo, env)
    run(["git", "config", "user.email", "test@example.com"], repo, env)


def run(command, cwd, env, check=True):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
        check=check,
    )


def yaml_quote(s):
    assert isinstance(s, str)
    # JSON quoted strings are also valid YAML
    return json.dumps(s)
