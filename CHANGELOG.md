# Changelog

All notable changes to Vision Macro Studio are documented here.

The project is currently in early development. Version numbers below describe
working snapshots rather than a promise of backward compatibility.

## [0.2.1] - 2026-09-07

- Fixed macro drag-and-drop so Qt no longer removes or overwrites a second row after the builder has already reordered the step list.
- Added a full-width teal insertion line that clearly shows whether a dragged step will be placed above or below a row.
- Deferred the data reorder until the native drop event finishes, preventing overlapping rows, disappearing steps, and unpredictable results.
- Added upward, downward, first-row, last-row, and no-op drop-index regression coverage while preserving automatic branch remapping.

## [0.2.0] - 2026-09-07

- Added a connected, scrollable Macro Flow view with labeled match, true/false, timeout, jump, repeat, and return routes.
- Added run-scoped variables and counters with Set Variable, Add Variable, and If Variable actions.
- Added reusable submacros through Call Macro, including nested execution, recursion protection, validation, overlay context, and bundled JSON export/import.
- Added explicit detection-failure branches so a timeout or maximum-check limit can stop, continue, or go to a chosen step.
- Advanced macro exports to format version 3 while retaining imports for versions 1 and 2.
- Added assisted labeling: the accepted model can propose non-duplicate boxes on a saved capture, and the user approves each suggestion before it is persisted.
- Added a dataset-quality dashboard with per-class coverage, average box size, position spread, recommendations, and near-duplicate screenshot detection.
- Added per-class mAP50/mAP50-95 persistence for new training runs, model notes, best-mAP identification, side-by-side model comparison, and saved confusion/training plots.
- Extended destination-safe reordering, validation, safe preview, logging, smoke tests, and packaged self-tests for the new v0.2.0 components.
- Kept existing projects, macros, models, and version 1/2 macro files backward-compatible.

## [0.1.18] - 2026-09-07

- Added drag-and-drop macro-step reordering with automatic branch-destination remapping.
- Upgraded duplicate, insert, delete, Move Up, and Move Down operations so numbered routes remain attached to their intended steps.
- Added optional readable names and comments to every macro step.
- Added colored, no-input section dividers and a dedicated Add Section workflow for organizing long macros.
- Added a Validate Macro report covering invalid and disabled destinations, missing project classes, unreachable steps, unbounded detection waits, and closed loops without a run limit.
- Blocked full and one-loop runs when validation contains errors while leaving warnings advisory and selected-step testing available.
- Added validation, organization, destination-remapping, persistence, and compatibility smoke tests.
- Kept existing macros backward-compatible; steps without names, comments, or sections continue unchanged.

## [0.1.17] - 2026-09-07

- Added a per-macro drawable detection region so inference can ignore irrelevant parts of the selected Watch source.
- Saved detection regions as normalized percentages so they scale with monitor resolution changes.
- Added absolute, Watch-relative, and application-window-relative coordinate modes to fixed mouse steps.
- Added coordinate picking that records a target window title/class and a percentage position inside that window.
- Resolved portable coordinates against the current monitor or current matching-window bounds at runtime.
- Added region-aware safe previews, coordinate resolution markers and logs, macro JSON validation, dependency-light tests, and packaged self-test coverage.
- Advanced exported macro JSON to format version 2 while continuing to import existing version 1 macro files.
- Kept existing macros backward-compatible as full-source detection with absolute coordinates.

## [0.1.16] - 2026-09-07

- Added per-step consecutive detection confirmations to reduce one-frame false positives.
- Added optional maximum detection-check limits in addition to time-based detection timeouts.
- Added clicked-object cooldowns that temporarily ignore the same class near the same screen position.
- Added an optional post-click wait for a detected object to disappear before continuing.
- Added stability settings to the Macro Builder summary, safe preview, logs, macro import/export validation, and smoke tests.
- Kept existing macros backward-compatible with stability features disabled by default.

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
