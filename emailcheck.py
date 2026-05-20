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
    [A-Za-z0-9._+]+

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


def find_emails(content, ignored_emails=()):
    for match in EMAIL_RE.finditer(content):
        email = match.group().decode("ascii")
        email_norm = email.casefold()
        if email_norm in ignored_emails or email_norm.endswith("@example.com"):
            continue
        yield email


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

    ignored_emails = read_ignored_emails(IGNORE_FILE)
    found = False
    for filename in args.filenames:
        for email in find_emails(filename.read_bytes(), ignored_emails):
            if not found:
                print("Detected strings which look like email addresses:\n")
            found = True
            print(f"{filename}: {email}")

    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
