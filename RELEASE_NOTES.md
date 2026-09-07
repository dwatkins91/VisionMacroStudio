# Vision Macro Studio v0.9.0 — Public Release Candidate

This release candidate combines the proven capture-to-macro workflow with the
public-release safeguards, documentation, and reproducible packaging needed for
broader testing.

## Highlights

- First-run welcome with workflow, safety, privacy, and storage guidance
- Check My Computer readiness report for dependencies, folders, displays, and GPU
- Built-in sample project with a completely input-free counter/branch tutorial
- Privacy-safe diagnostic ZIP and scrubbed local crash reports
- Advanced macro debugger, stability controls, regions, portable coordinates,
  variables, counters, submacros, validation, flow view, and safe drag reordering
- Assisted labeling, dataset-quality analysis, model lineage, reports, notes, and
  side-by-side per-class model comparison
- Automated source checks, CodeQL, tagged Windows builds, packaged self-test,
  SHA-256 checksum, and build provenance attestation
- GNU AGPL-3.0-or-later licensing under Dillard Watkins with exact-source and
  third-party notices included in the portable package

## Important release-candidate warning

The Windows binaries are not yet code-signed. Smart App Control or an
organization's application-control policy may block the executable or a native
dependency. Do not disable Windows security protections to run it. Code signing
and expanded clean-machine testing remain v1.0.0 release gates.

## Download and verify

1. Download `VisionMacroStudio-Portable-v0.9.0.zip` and `SHA256SUMS.txt` from
   this release.
2. Compare the ZIP's SHA-256 hash with the published value.
3. Extract the entire ZIP to a short normal path such as `D:\VMS-0.9.0`.
4. Read `START_HERE.txt`, then open `VisionMacroStudio.exe`.
5. Complete Welcome and run **Help → Check My Computer**.

Please use the structured GitHub issue form for bugs. Review diagnostic ZIPs
before attaching them publicly and never share private captures, credentials,
or model files unintentionally.
