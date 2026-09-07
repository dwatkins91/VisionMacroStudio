# Public release checklist

Use this checklist for a release candidate and repeat it against the exact ZIP
downloaded from GitHub Releases.

## Source and policy

- [ ] Version matches in `app/__init__.py`, README, changelog, portable guide,
      source offer, and release tag.
- [ ] `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `SOURCE_OFFER.txt` are included.
- [ ] `py tests\smoke_test.py` passes.
- [ ] `py -m compileall app tests tools` passes.
- [ ] GitHub test and CodeQL workflows pass.
- [ ] Repository contains no projects, captures, model weights, logs, secrets,
      environments, or build directories.

## Clean Windows test

- [ ] Test on a Windows account and folder that were not used to build it.
- [ ] Extract the ZIP fully; do not run from inside the ZIP.
- [ ] Confirm the eye icon and version 0.9.0 RC title.
- [ ] Complete first-run onboarding.
- [ ] Run Check My Computer and save/copy its report.
- [ ] Create the sample project and run the safe counter tutorial.
- [ ] Create, close, and reopen a new project.
- [ ] Capture and label a test object.
- [ ] Split, train, test, accept, and compare a small model.
- [ ] Safe-preview and run a short macro with F12 emergency stop.
- [ ] Export/import a macro and a project.
- [ ] Create and inspect a diagnostic package.
- [ ] Confirm no source-machine project path appears in settings or output.

## Distribution

- [ ] Tag the exact tested commit `v0.9.0`.
- [ ] Automated Windows build and packaged self-test pass.
- [ ] Release ZIP checksum matches `SHA256SUMS.txt`.
- [ ] Download the public release asset and repeat the clean test.
- [ ] Mark the GitHub release as a **pre-release** while it remains unsigned.
- [ ] State clearly that Smart App Control may block unsigned native components.

Code signing and clean-machine trust testing remain release gates for v1.0.0.
