# GitHub repository setup

The repository files automate tests, dependency updates, CodeQL analysis, and
tagged Windows release-candidate builds. A repository owner must still enable
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

## Publish v0.9.0

After locally validating the source commit:

```powershell
git tag -a v0.9.0 -m "Vision Macro Studio v0.9.0 public release candidate"
git push origin v0.9.0
```

The tag starts the Windows release workflow. It verifies version metadata,
runs tests, builds and self-tests the portable package, calculates its SHA-256
checksum, creates a provenance attestation, and creates or updates a GitHub
pre-release.

Download the resulting ZIP from the public Releases page and complete
[`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) against that exact download.
