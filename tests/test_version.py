import pathlib
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
