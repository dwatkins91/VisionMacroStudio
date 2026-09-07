# Vision Macro Studio v1.0.0 — First Public Release

Vision Macro Studio 1.0.0 is the first complete public release of the proven
capture-to-macro workflow. It includes a standard Windows installer, a portable
edition, public source, automated tests, checksums, and build provenance.

## Highlights

- Capture and label multiple screen objects with global-hotkey and multi-monitor support
- Train, refine, test, compare, and explicitly accept local YOLO models
- Build visual macros with detection branches, stability controls, search regions,
  portable coordinates, variables, counters, reusable submacros, and recovery routes
- Preview steps without input, run one step or loop, validate macro logic, inspect the
  connected flow view, and stop live automation with F12
- Use assisted labeling, dataset-quality analysis, per-class model metrics, diagnostics,
  a first-run guide, and a safe built-in sample project
- Install normally with `VisionMacroStudio-Setup-v1.0.0.exe`, or use the self-contained
  portable ZIP without installing Python or its libraries
- Verify both downloads with `SHA256SUMS.txt` and GitHub build-provenance attestations
- Inspect, modify, and redistribute the complete AGPL-3.0-or-later source under
  Dillard Watkins

## Important unsigned-release notice

The Setup EXE and portable application are not Authenticode signed. Windows may
display **Unknown publisher**, Microsoft Defender SmartScreen may warn, and Smart App
Control or an organizational application-control policy may block installation or a
native dependency. Do not disable Windows security protections to run the application.

## Download and install

1. Under **Assets**, download `VisionMacroStudio-Setup-v1.0.0.exe` and
   `SHA256SUMS.txt`.
2. Compare the installer's SHA-256 hash with the published value.
3. Run the installer and review the unsigned-release notice before continuing.
4. Open Vision Macro Studio, complete Welcome, and run **Help → Check My Computer**.

For a no-install alternative, download `VisionMacroStudio-Portable-v1.0.0.zip`,
extract the entire ZIP to a short normal path such as `D:\VMS-1.0.0`, read
`START_HERE.txt`, and open `VisionMacroStudio.exe`.

Please use the structured GitHub issue form for bugs. Review diagnostic ZIPs before
attaching them publicly, and never share private captures, credentials, datasets, or
model files unintentionally.
