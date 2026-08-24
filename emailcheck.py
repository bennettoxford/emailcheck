"Find email-like strings in files"

import argparse
import os
import pathlib
import re
import subprocess
import sys


# This is a deliberately conservative regex: there are strings which are technically
# valid email addresses which it will not match. That's OK in this context because the
# case we want to guard against is having multiple addresses commited and the chances of
# them all being "weird" addresses is low, and the costs of false positive matches in
# terms of development friction is high.
EMAIL_RE = re.compile(
    rb"""
    # Local part: alphanumerics or one of . _ +
    # To improve performance of the regex on long hex/base64 encoded strings we only
    # match the last 64 characters. This will cover most reasonable addresses, and if an
    # address is longer it will still match, we'll just report a truncated version.
    [A-Za-z0-9._+]{1,64}

    @

    # Domain: one or more labels, each label:
    #   - starts and ends with alphanumeric
    #   - may contain hyphens in the middle
    # This excludes IPv4/IPv6 literals because the domain must end in a
    # letter-only TLD and must contain at least one dot.
    (?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,63}[A-Za-z0-9])?\.)+
    [A-Za-z]{2,63}
    """,
    re.VERBOSE,
)


IGNORE_FILE = pathlib.Path(".emailcheck_ignore")

DEFAULT_IGNORE = {"@example.com"}


def find_emails(content, ignored_emails=()):
    # We want to avoid scanning the binary files which occasionally appear in our repos
    # e.g. images, ZIP files, XLSX files. It's not only wasteful to scan these, which
    # are often larger than typical text files, but they also contain annoying false
    # positives (e.g. sequences like "Xjz@E.gnE" and "9@l.mF")
    if is_binary_format(content):
        return

    for match in EMAIL_RE.finditer(content):
        email = match.group().decode("ascii")
        email_norm = email.casefold()
        domain_norm = "@" + email_norm.partition("@")[2]
        if email_norm in ignored_emails or domain_norm in ignored_emails:
            continue
        yield email


def is_binary_format(content):
    # NUL bytes are a sure sign of non-text content. We only bother checking the first
    # 4K as if it is a binary format we'll most likely see NUL bytes by then and we
    # don't want to waste CPU scanning more than we need.
    return content.find(b"\x00", 0, 4096) != -1


def read_ignored_emails(path):
    if not path.exists():
        return set()

    ignored_emails = set()
    for line in path.read_text().splitlines():
        line = line.partition("#")[0]
        for email in line.split():
            ignored_emails.add(email.casefold())
    return ignored_emails


def get_commits_between_git_refs(from_ref, to_ref):
    result = subprocess.run(
        ["git", "rev-list", f"{from_ref}..{to_ref}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def get_additions_in_commit(commit_id):
    result = subprocess.run(
        [
            "git",
            "show",
            "--format=",
            "--no-color",
            "--no-ext-diff",
            "--no-renames",
            "--unified=0",
            commit_id,
        ],
        check=True,
        capture_output=True,
    )
    for chunk in result.stdout.split(b"\n+++ b/")[1:]:
        encoded_filename, _, diff = chunk.partition(b"\n")
        filename = os.fsdecode(encoded_filename)
        content = b"".join(
            line[1:] for line in diff.splitlines(keepends=True) if line.startswith(b"+")
        )
        yield filename, content


def get_additions_between_git_refs(from_ref, to_ref):
    for commit_id in get_commits_between_git_refs(from_ref, to_ref):
        for filename, content in get_additions_in_commit(commit_id):
            yield f"{commit_id[:8]} {filename}", content


def check_for_email_addresses(sources, ignored_emails, log):
    found = False
    for filename, content in sources:
        for email in find_emails(content, ignored_emails):
            if not found:
                log("Detected strings which look like email addresses:\n")
            found = True
            log(f"{filename}: {email}")

    if found:
        log(
            "\n"
            "This operation was blocked to prevent a possible data leak. If these\n"
            "legitimately belong in this repo then you can add them to an\n"
            "`.emailcheck_ignore` file in the project root directory.\n"
            "\n"
            "To ignore all addresses from a particular domain use: @example-domain.com"
        )
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="*", type=pathlib.Path)
    args = parser.parse_args(argv)

    from_ref = os.environ.get("PRE_COMMIT_FROM_REF")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF")

    ignored_emails = read_ignored_emails(IGNORE_FILE).union(DEFAULT_IGNORE)

    if from_ref or to_ref:
        if not (from_ref and to_ref):
            parser.error(
                "PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF environment "
                "variables must both be set if either is"
            )
        sources = get_additions_between_git_refs(from_ref, to_ref)
    elif args.filenames:
        sources = (
            (str(filename), filename.read_bytes()) for filename in args.filenames
        )
    else:
        parser.error("the following arguments are required: filenames")

    found = check_for_email_addresses(sources, ignored_emails, log=print)
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
