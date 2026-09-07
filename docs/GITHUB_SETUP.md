# GitHub repository setup

The repository files automate tests, dependency updates, CodeQL analysis, and
tagged Windows release builds. A repository owner must still enable
the matching GitHub settings.

## Recommended settings

1. Open **Settings → Code security and analysis**.
2. Enable Dependency graph, Dependabot alerts, Dependabot security updates,
   secret scanning, and push protection where GitHub makes them available.
3. Open **Settings → Rules → Rulesets** and protect `main` after the initial
   workflows have completed successfully.
4. Require the Tests and CodeQL checks for pull requests.
5. Keep force pushes and branch deletion disabled for `main`.
6. Confirm **Settings → Actions → General → Workflow permissions** permits the
   release workflow to create a GitHub release. The workflow itself requests
   only the permissions it uses.
7. Confirm private vulnerability reporting is enabled under Security settings.

## Publish v1.0.0

Before creating the tag, open **Actions → Windows Release → Run workflow** on
`main`. The manual run builds, installs, self-tests, uninstalls, checksums, and
attests both Windows packages without creating a public release. Download its
workflow artifact and test the Setup EXE on Windows.

After the manual run and local validation succeed:

```powershell
git tag -a v1.0.0 -m "Vision Macro Studio v1.0.0"
git push origin v1.0.0
```

The tag starts the Windows release workflow. It verifies version metadata,
runs tests, builds and self-tests the portable package and Setup EXE, calculates
SHA-256 checksums, creates provenance attestations, and creates or updates the
GitHub release.

Download the resulting Setup EXE and ZIP from the public Releases page and complete
[`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) against that exact download.
