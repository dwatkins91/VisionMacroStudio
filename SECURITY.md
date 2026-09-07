# Security policy

## Supported versions

Security fixes are applied to the newest public release candidate or stable
release. Older development snapshots are not supported.

| Version | Supported |
| --- | --- |
| 0.9.x | Yes |
| 0.2.x and earlier | No |

## Reporting a vulnerability

Please use the repository's **Security → Report a vulnerability** option to
open a private GitHub security advisory. Do not publish an exploitable issue,
credential, private capture, trained model, or diagnostic package in a public
issue.

Include the affected version, Windows version, reproduction steps, expected
behavior, actual behavior, and whether the issue can cause unintended input,
file access, archive extraction, or disclosure of captured content.

This is a volunteer project. Reports will be acknowledged when reviewed, but
no response or repair deadline is guaranteed.

## Security boundaries

- Macros intentionally send mouse and keyboard input after the user starts a
  live run. Safe Step Preview does not send input.
- Imported macro files are data, but users should still inspect and validate
  them before running because their steps can type text, press keys, and click.
- Project ZIP imports reject absolute paths and parent-directory traversal.
- Diagnostic packages exclude captures and model files and redact typed-text
  contents, window titles, and known local paths. Users should review the ZIP
  before sharing it.
- Current release-candidate binaries are unsigned. Do not disable Windows
  security protections to run them.
