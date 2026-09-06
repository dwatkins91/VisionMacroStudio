# Vision Macro Studio

Version 0.1.14 keeps the macro step editor's modal Save session alive while its
coordinate picker is open and confirms the persisted step in the Macro Builder.
Version 0.1.13 adds a visible selected-coordinate confirmation. Version
0.1.12 adds click/hover screen-coordinate pickers to macro steps and
versioned JSON macro import/export. Version 0.1.11 adds randomized minimum/maximum wait ranges, randomized
detection timeouts, and detected-object right-clicks. Version 0.1.10 adds a configurable random pixel offset to fixed-coordinate
left-click, double-click, and right-click macro steps. Version 0.1.9 adds a
selectable training starting point, allowing a new model
to fine-tune from any existing project model while preserving model lineage.
Version 0.1.8 aligns macro detection with Test Model by adding a per-macro
monitor source, forgiving class-name matching, visible accepted-model status,
and overlay feedback for detections that are below the step threshold. Version
0.1.7 corrected the packaged runtime location of the application icon.
Version 0.1.6 added a guided, verified Windows portable-build workflow so the
application can be shared with people who do not have Python installed. Version
0.1.5 added a custom binary-eye application icon and a slim illuminated
divider between navigation and page content. Version 0.1.4 added a movable,
always-on-top two-line macro status overlay and a
persisted per-macro automatic stop time. Version 0.1.3 added priority fallback
clicks, multi-object conditional branches, unconditional Go To steps, and
detailed macro decision logs. Version 0.1.2 fixed Macro Builder steps
disappearing after Save and pinned the
Windows-compatible Torch 2.13.0/torchvision 0.28.0 pair. Version 0.1.1 fixed
RGB/BGR preprocessing during saved-image, live-screen, and macro inference.

## Build a portable Windows edition

Run the builder from the same 64-bit Windows Python environment that already
opens Vision Macro Studio. For the standard in-project environment:

```powershell
.\.venv\Scripts\python.exe tools\build_windows_portable.py
```

If your `.venv` is one folder above the source, use:

```powershell
& "..\.venv\Scripts\python.exe" tools\build_windows_portable.py
```

The builder installs PyInstaller into that private environment if necessary,
creates a one-folder Windows application, launches a packaged self-test, and
produces `release\VisionMacroStudio-Portable-v0.1.14.zip`. It optionally accepts
an exported project ZIP so a recipient can import your trained model and macros.
The build can take 10–30 minutes and may be well over 1 GB because it contains
Python, Qt, OpenCV, PyTorch, Torchvision, and Ultralytics.

The portable application must be built on Windows; PyInstaller output is tied
to the operating system and architecture used for the build. The generated app
is unsigned, so Smart App Control may block it on some Windows 11 computers. A
valid code-signing certificate is the reliable distribution path for machines
where Smart App Control is enabled.

Vision Macro Studio is a Windows-first desktop application that turns a screen object into a reusable visual automation target:

**Capture it → name it → gather examples → train → test → accept → use it in a macro**

The project is intentionally structured as an application, not a pile of example scripts. It uses PySide6 for the interface, MSS/Pillow for capture, Ultralytics YOLO for fine-tuning and inference, and pynput for global hotkeys and automation.

## Quick start on Windows

1. Install 64-bit Python 3.10 or newer from python.org. During installation, select **Add Python to PATH**.
2. Extract this entire folder somewhere writable, such as Documents.
3. Double-click `run_app.bat`.
4. The first launch creates a private `.venv` and installs the required packages. PyTorch and PySide6 are large, so the first setup can take several minutes.
5. Later launches reuse that environment and start directly.

If you prefer to install without launching, use `install_only.bat`.

## First project workflow

1. Open **Project**, choose **New Project**, and give it a name.
2. Open **Capture**. Put the target application on screen and press **F8**, or click **Capture Object Now**.
3. Drag a box around an object. Choose or type its class name. Add more boxes if useful, then press **Enter** to save the full screenshot and all boxes. Escape cancels; Backspace removes the latest box.
4. Repeat with different positions, backgrounds, sizes, and appearances.
5. Open **Dataset**, preview captures, remove bad screenshots, and choose **Automatic Split**. The data check offers beginner-friendly warnings without blocking training.
6. Open **Train** and use the recommended pretrained Nano model at first. For later refinement, **Start from** can instead load any existing project model and fine-tune it against the entire current dataset. GPU acceleration is used when chosen and available; CPU works but is slower.
7. When training finishes, test a saved image or a live monitor in **Test Model**.
8. In **Models**, select the best version and choose **Accept Model**.
9. In **Macros**, make a macro and add object-based actions such as Wait for Object or Click Object. Use Run Selected Step while debugging.
10. **F12** or the red **Emergency Stop** button stops the macro and releases held input.

## Refining an existing model

The Train page's **Start from** list contains the pretrained YOLO base and all
models saved in the open project. Existing models show their accepted status
and mAP50 when available. Selecting an existing model disables **Model size**
because the checkpoint already determines its architecture.

Refinement loads the selected model's learned weights, starts a new training
run, and trains against the entire current dataset. It does not overwrite or
resume the old run. The result is saved as a separate candidate model, and the
Models page records its starting point. This makes it safe to try a shorter run
from a strong model and return to the earlier version if the new result is not
better.

## Conditional macro actions

- **Click First Available** accepts comma-separated object names in priority
  order. If the first object is absent but the second is visible, only the
  second object is clicked.
- **Wait For Any Object** watches all listed objects in one detection pass. Add
  one destination step number per object; use `0` to continue to the next row.
- **Go To Step** jumps directly to another numbered row. It can create an
  intentional continuous loop that remains interruptible with **F12**.
- **Click**, **Double Click**, and **Right Click** target a fixed screen X/Y
  position. **Random pixel offset** moves the actual click independently by up
  to the chosen number of pixels on each axis; use `0 px` for an exact click.
- **Right Click Object** detects an object, moves to the chosen position inside
  its box, and right-clicks it.
- Screen-coordinate actions provide **Pick by Click** and **Pick by Hover**.
  Click mode uses a full-desktop overlay that prevents the selection click from
  reaching the underlying application. Hover mode captures the cursor after a
  three-second countdown. Both show a crosshair and live X/Y coordinates;
  Escape cancels.
  After selection, confirm that the visible **Selected coordinate** row shows
  the intended X/Y values before saving the step.
- Wait steps and detection timeouts accept minimum and maximum times. The app
  chooses a new duration inside the range whenever that step runs. A randomized
  **Wait For Any Object** timeout continues watching for its target objects
  throughout the delay and only advances when the selected timeout expires.

Example: Click First Available can try `Primary_Button, Fallback_Button`.
Wait For Any Object can watch `Continue_Message, Restart_Message` with
destinations `3, 5`, sending each detected message to a different part of the
macro. The Logs page records the detected object, confidence, bounding box,
fallback choice, and branch destination.

## Sharing macros

The Macro Builder's **Export Macro** button saves the selected macro as a
versioned `.vmsmacro.json` file. It includes the step order, object names,
timing, coordinates, offsets, monitor selection, and macro time limit. Models,
screenshots, and project data are not included.

Use **Import Macro** in any open project to add a shared macro. Imported macros
receive a unique name when needed. The app warns when referenced object classes
are missing, the saved monitor is unavailable, or coordinate steps need to be
verified for a different screen layout. Raw JSON containing a valid macro name
and step list is also accepted, allowing generated macro outlines to be
imported directly.

## Running status and automatic stop

The Macro Builder's **Show compact status overlay** option displays an
always-on-top two-line window while a macro runs. It shows the current numbered
step and the latest detection result with confidence. Drag the overlay anywhere
on screen; its position is remembered. Move it away from important targets so
it does not cover the pixels the model needs to see.

Each macro has its own **Stop after** value in minutes. `No limit` preserves the
original behavior. A positive value safely interrupts detection polling, waits,
mouse travel, and continuous loops when the selected duration expires.

Default hotkeys are configurable in Settings:

| Action | Default |
|---|---|
| Capture object | F8 |
| Start coordinate recording | F6 |
| Stop coordinate recording | F7 |
| Run selected macro | F9 |
| Emergency stop | F12 |

## Architecture

- `app/core`: durable JSON settings and project management.
- `app/capture`: multi-monitor screenshots, dimmed labeling overlay, and global hotkeys.
- `app/vision`: quality checks, YOLO dataset export, worker-thread training, inference, and model versions.
- `app/automation`: macro recording and execution with object targeting, timeouts, repeat steps, smooth mouse movement, and emergency input release.
- `app/gui`: the PySide6 shell and focused pages for the end-to-end workflow.

Each project contains `project.json`, screenshots, optional review crops, YOLO exports, trained models, logs, and saved macros. Models are versioned and never automatically overwrite older versions.

## Implemented in this MVP

- Project create/open/rename/delete/import/export
- Global-hotkey capture with a dimmed snipping overlay
- Multiple labeled boxes on one complete screenshot plus optional crops
- Class management, preview, deletion, and stratified-ish train/validation splitting
- Dataset quality warnings for sample count, imbalance, location, size, and missing validation data
- Nano/Small/Medium YOLO fine-tuning in a worker thread with progress and safe-stop request
- Selectable pretrained or existing-model training starting point with saved lineage
- Saved-image testing and live full-desktop/monitor testing with confidence, FPS, and inference timing
- Versioned model library with explicit acceptance
- Row-based macro editor with wait/click-object, fallback selection, conditional branches, go-to, disappearance, keyboard, text, delays, coordinate clicks/moves, repeat, and stop
- Randomized wait/timeout ranges and detected-object right-clicks
- Object-relative click positions, randomized offsets, and smooth randomized mouse travel
- Fixed-coordinate clicks with optional random pixel offsets and logged final coordinates
- Full-desktop click/hover coordinate picker for every screen X/Y step
- Versioned JSON macro import/export with validation and compatibility warnings
- Traditional click/key recorder
- Draggable two-line live status overlay, debug status, single-step execution, log saving, run hotkey, timed automatic stop, and emergency stop

## Current practical limits

- Live testing captures an entire monitor or virtual desktop. Selecting one application window or an arbitrary live region is not in this MVP.
- The macro builder uses row controls and Move Up/Move Down instead of drag-and-drop blocks.
- Coordinate recording captures clicks and key presses with delays; it intentionally does not save every raw mouse-movement event.
- Training progress reports epochs and overall percentage. Detailed loss/validation plots are produced by Ultralytics inside the project training-run folder rather than graphed in the app.
- GPU use requires a compatible NVIDIA setup supported by the installed PyTorch build. If GPU mode fails, select CPU or Automatic.

## Verification status

### Verified in the build environment

- Every Python module passes `compileall` syntax compilation.
- Focused static checks for undefined names, invalid syntax, and broken imports pass.
- `tests/smoke_test.py` creates a project, saves labeled full-screen images and crops, splits data, generates YOLO images/labels/YAML, renames a class, registers/accepts/deletes a model record, exports a project ZIP, imports it again, and confirms the saved data.

### Requires testing on your Windows computer

- Opening and visually inspecting the PySide6 GUI. The Linux build runner does not contain its required EGL display library.
- Real multi-monitor screen capture and overlay placement.
- Global hotkeys, traditional input recording, automated mouse/keyboard control, and F12 emergency stop.
- Downloading YOLO weights, full model training, GPU selection, and live inference against your actual screen.

Run `python tests/smoke_test.py` from the project folder any time you want to repeat the dependency-light persistence/export test.

## Safety and responsible use

Automation can click or type into the wrong window if the screen changes. Test one step at a time, keep F12 available, and do not use the application to bypass access controls, anti-cheat systems, terms of service, or safeguards. The application does not include stealth or background evasion features.

## Data and privacy

Screen captures and models stay in the project folder you choose. Captures can contain private information visible on screen; review them before sharing or exporting a project.
