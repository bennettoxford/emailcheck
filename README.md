# emailcheck

`emailcheck` is a [pre-commit](https://pre-commit.com/) hook that checks staged files
for strings which look like personal email addresses.

Email addresses are assumed to be ASCII-encoded without attempting to guess the
surrounding text encoding. Binary files are ignored.

False positives can be excluded by adding them to a `.emailcheck_ignore` file.

## Installation

Assuming `pre-commit` in already installed in the target repository you can install this
hook by updating the `.pre-commit-config.yaml` file.

First ensure that `pre-commit` will install `pre-push` hooks:
```yaml
default_install_hook_types:
  - pre-commit
  - pre-push
```

Then add an entry to the `repos` list:
```yaml
repos:
  - repo: https://github.com/bennettoxford/emailcheck
    rev: v1
    hooks:
      - id: emailcheck
```

## Usage

Once installed, `emailcheck` runs automatically when you commit or push. If it finds an
email-like string, it prints the matching filename and address, then exits non-zero so
the commit or push is blocked:

```text
Detected strings which look like email addresses:

contacts.txt: alice@test.org

If these are not Personally Identifiable Information and legitimately
belong in this repo then you can add them to an `.emailcheck_ignore` file
in the project root directory.

To ignore all addresses from a particular domain use: @example-domain.com
```

You can also run it manually:

```sh
pre-commit run emailcheck --all-files
```

## Ignoring Addresses

To allow specific addresses, add a `.emailcheck_ignore` file in the root of the
repository being checked:

```text
# fixture addresses
alice@test.org
bob@test.org carol@test.org  # whitespace-separated addresses are supported

# Entire domains can be ignored where appropriate
@my-internal-domain.org
```

Blank lines and whitespace are ignored. Anything after `#` on a line is treated as a
comment. Address matching is case-insensitive.

The domain `@example.com` is automatically ignored.

## Developer docs

Please see the [additional information](DEVELOPERS.md).
