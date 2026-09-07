# Changelog

All notable changes to Vision Macro Studio are documented here.

The project is currently in early development. Version numbers below describe
working snapshots rather than a promise of backward compatibility.

## [0.1.15] - 2026-09-07

- Added a safe, single-frame preview for any selected macro step.
- Added annotated detection previews, configured-coordinate markers, and explicit branch reasoning without sending mouse or keyboard input.
- Added a live one-loop run that stops before control returns to step 1.
- Kept the existing selected-step live run and corrected its displayed/logged step number.
- Added visible live decision explanations to the Macro Builder.

## [0.1.14] - 2026-09-03

- Kept the macro-step editor's Save session active while the coordinate picker is open.
- Confirmed that coordinates selected by the picker persist in the saved macro step.

## [0.1.13] - 2026-09-03

- Added a visible selected-coordinate confirmation to coordinate-based macro steps.

## [0.1.12] - 2026-09-03

- Added click and hover coordinate pickers to every fixed X/Y macro action.
- Added versioned `.vmsmacro.json` macro import and export.
- Added compatibility warnings for missing classes, monitors, and coordinate layouts.

## [0.1.11] - 2026-09-03

- Added randomized minimum/maximum ranges to waits and detection timeouts.
- Added detected-object right-click actions.

## [0.1.10] - 2026-09-03

- Added configurable random pixel offsets to fixed-coordinate left-click, double-click, and right-click steps.

## [0.1.9] - 2026-09-03

- Added a selectable model starting point for training.
- Added safe fine-tuning from an existing project model without overwriting the source model.
- Added model-lineage information to saved model records.

## [0.1.8] - 2026-09-03

- Added a per-macro monitor source.
- Aligned macro detection behavior with Test Model.
- Added forgiving class-name matching and visible accepted-model status.
- Added overlay feedback for detections below the active step threshold.

## [0.1.7] - 2026-09-02

- Corrected the packaged runtime location of the application icon.

## [0.1.6] - 2026-09-02

- Added a guided PyInstaller workflow for a verified, portable Windows build.
- Added an optional exported demo project to portable packages.
- Added a packaged self-test covering GUI, capture, PyTorch, and Ultralytics imports.

## [0.1.5] - 2026-09-02

- Added the binary-eye application icon.
- Added an illuminated divider between navigation and page content.

## [0.1.4] - 2026-09-02

- Added a movable, always-on-top, two-line macro status overlay.
- Added a saved per-macro automatic stop time.

## [0.1.3] - 2026-09-02

- Added priority fallback object clicks.
- Added multi-object conditional branches and unconditional Go To steps.
- Expanded macro decision and detection logging.

## [0.1.2] - 2026-09-02

- Fixed Macro Builder steps disappearing after Save.
- Pinned the Windows-compatible Torch 2.13.0 and Torchvision 0.28.0 pair.

## [0.1.1] - 2026-09-02

- Corrected RGB/BGR preprocessing for saved-image, live-screen, and macro inference.

## [0.1.0] - 2026-09-01

- Added project creation, import, export, and durable JSON settings.
- Added global-hotkey screen capture and multi-box object labeling.
- Added YOLO dataset creation, training, validation, testing, and model acceptance.
- Added the row-based visual macro builder, recorder, smooth mouse movement, hotkeys, logs, and emergency stop.
