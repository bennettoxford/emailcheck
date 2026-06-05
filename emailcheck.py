"Find email-like strings in files"

import argparse
import pathlib
import re
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
    (?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    ignored_emails = read_ignored_emails(IGNORE_FILE).union(DEFAULT_IGNORE)
    found = False
    for filename in args.filenames:
        for email in find_emails(filename.read_bytes(), ignored_emails):
            if not found:
                print("Detected strings which look like email addresses:\n")
            found = True
            print(f"{filename}: {email}")

    if found:
        print(
            "\n"
            "If these are not Personally Identifiable Information and legitimately\n"
            "belong in this repo then you can add them to an `.emailcheck_ignore` file\n"
            "in the project root directory."
        )
        return 1
    else:
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
