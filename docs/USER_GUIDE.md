# Vision Macro Studio user guide

## Start safely

1. Open **Help → Check My Computer**. Resolve every red failure before training
   or running macros. Yellow items are advisory.
2. Create a new project, open an existing project, or choose **Create Sample**.
3. Keep **F12** available as the emergency-stop hotkey.
4. Test automation with **Safe Step Preview**, then **Run Selected Step**, then
   **Run One Loop**, before starting an unattended loop.

## Build a detector

1. Put the target application in its normal position and open **Capture**.
2. Press **F8**, draw boxes tightly around the objects, and assign stable class
   names.
3. Capture varied examples: different positions, sizes, backgrounds, and visual
   states.
4. Review labels in **Dataset**, choose **Automatic Split**, and check the
   Quality Dashboard.
5. Start with a Nano model in **Train**. An existing accepted model can be used
   as the starting point for a shorter refinement run.
6. Test saved screenshots and the live screen. Compare per-class results, not
   only overall mAP50.
7. Accept the model that behaves most reliably on real live-screen examples.

## Build and debug a macro

- Give steps readable names and add colored sections.
- Prefer Watch-relative or application-window-relative coordinates when a
  macro needs to work at different resolutions.
- Limit detection to a drawn region when a message or object appears in one
  predictable area.
- Use consecutive detections, cooldowns, and wait-until-disappears for unstable
  visual states.
- Add timeout destinations and an overall macro time limit.
- Choose **Validate Macro** before every full run.
- Use Flow View to inspect branches, counters, loops, and submacro returns.

## Share safely

Exported `.vmsmacro.json` files contain macro structure and settings, but not
models or screenshots. Review fixed coordinates, window-relative targets, and
typed-text steps before sharing or importing.

Project ZIPs are complete backups and may contain private captures and large
trained models. Treat them as private unless deliberately reviewed.

For support, use **Logs → Create Diagnostic Package**. Review the ZIP before
adding it to a GitHub issue.

## Storage and recovery

Open **Settings** to see the configured project directory. Each project is a
normal folder with a `project.json` file. Back up important projects separately
from the application source. GitHub stores the application code; it does not
store local projects ignored by `.gitignore`.
