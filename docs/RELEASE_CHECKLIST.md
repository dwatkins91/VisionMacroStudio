# Public release checklist

Use this checklist for a public release and repeat it against the exact Setup EXE
and portable ZIP downloaded from GitHub Releases.

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
- [ ] Confirm the eye icon and version 1.0.0 title with no RC label.
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

## Installed edition

- [ ] Install `VisionMacroStudio-Setup-v1.0.0.exe` for the current user.
- [ ] Confirm the unsigned-publisher warning is accurate and understandable.
- [ ] Confirm Start menu and optional desktop shortcuts open the application.
- [ ] Run Check My Computer from the installed application.
- [ ] Confirm personal projects are not installed with the application.
- [ ] Uninstall from Windows Settings and confirm project data remains intact.

## Distribution

- [ ] Manually run the Windows Release workflow on `main` before tagging.
- [ ] Download and test the unsigned Setup EXE from that workflow artifact.
- [ ] Tag the exact tested commit `v1.0.0`.
- [ ] Automated Windows portable and installer self-tests pass.
- [ ] Setup EXE and portable ZIP checksums match `SHA256SUMS.txt`.
- [ ] Download both public release assets and repeat the relevant clean tests.
- [ ] Publish it as a normal GitHub release, not a pre-release.
- [ ] State clearly that Smart App Control may block unsigned native components.
