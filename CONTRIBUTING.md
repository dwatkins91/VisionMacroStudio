# Contributing

Focused bug reports, documentation improvements, tests, and pull requests are
welcome.

## Before opening a pull request

1. Fork the repository and create a focused branch.
2. Keep user projects, screenshots, model weights, logs, environments, and
   build output out of Git.
3. Preserve backward compatibility for existing project and macro JSON where
   practical.
4. Add or update dependency-light smoke coverage for behavior changes.
5. Run:

   ```powershell
   py -m compileall app tests tools
   py tests\smoke_test.py
   ```

6. Explain what changed, why, and how it was validated.

Do not add stealth, security-evasion, anti-detection, credential-handling, or
access-control-bypass behavior. Automation should remain visible, stoppable,
and under the user's direct control.

By submitting a contribution, you agree that it may be distributed under the
project's GNU Affero General Public License version 3 or later. Retain existing
copyright and third-party notices.
