# Example macros

These examples contain generic class names and no saved screen coordinates,
monitor identifiers, screenshots, models, or personal project information.

Import an example from the **Macros** page after opening a project. The app may
warn that the example's object classes do not exist. Create matching classes or
edit the imported steps to use the classes from your own model.

Use **Safe Step Preview** first to verify detection thresholds and branching
without sending input. **Run Selected Step** is a live test and can send the
configured mouse or keyboard action.

The priority-branch example also demonstrates consecutive confirmations, a
maximum detection-check count, a clicked-object cooldown, and a post-click
wait for the selected object to disappear. It also includes readable step
names, a comment, and a colored Section divider introduced in version 0.1.18.

The counter-submacro example uses macro format version 3. It bundles a reusable
submacro, sets and increments a counter, and follows a true/false variable
branch. Importing the one file adds both macros to the open project.

The portable-coordinate template demonstrates a Watch-relative coordinate. Its
movement step is disabled until you pick, preview, and enable your own location.
