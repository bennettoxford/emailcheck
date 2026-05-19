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


def find_emails(content):
    for match in EMAIL_RE.finditer(content):
        email = match.group()
        if email.lower().endswith(b"@example.com"):
            continue
        yield email.decode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    found = False
    for filename in args.filenames:
        for email in find_emails(filename.read_bytes()):
            if not found:
                print("Detected strings which look like email addresses:\n")
            found = True
            print(f"{filename}: {email}")

    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
