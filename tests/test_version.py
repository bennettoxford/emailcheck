import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_version_file_contains_valid_git_tag():
    version_path = ROOT / "VERSION"

    assert version_path.exists()

    tag = version_path.read_text().strip()
    assert tag
    subprocess.run(
        ["git", "check-ref-format", "--allow-onelevel", tag],
        check=True,
    )


def test_readme_revision_matches_version_file():
    version = (ROOT / "VERSION").read_text().strip()
    readme = (ROOT / "README.md").read_text()

    match = re.search(r"^[ \t]*rev:[ \t]*(\S+)", readme, re.MULTILINE)

    assert match is not None
    assert match.group(1) == version
