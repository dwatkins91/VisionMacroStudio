VISION MACRO STUDIO - PORTABLE WINDOWS EDITION
================================================

1. Extract the complete ZIP to a normal folder.
2. Open the VisionMacroStudio folder.
3. Double-click VisionMacroStudio.exe.

Python and the supporting libraries are already included. Keep the EXE and the
_internal folder together; moving only the EXE will prevent the app from opening.

If Demo_Project.zip is included, open Vision Macro Studio, select Project >
Import, and choose that ZIP. The demo project may contain its own trained model,
captures, and macros.

Safety: F12 is the default emergency stop for a running macro. Only run macros
against an application and computer you are authorized to control.

Macro debugging: Safe Step Preview inspects one screen frame and explains the
selected step without sending mouse or keyboard input. Run Selected Step and
Run One Loop are live tests and can send their configured inputs.

Detection stability: Individual visual steps can require consecutive matches,
limit detection checks, ignore a recently clicked object for a cooldown period,
and wait for a clicked object to disappear. Existing macros keep their previous
behavior until these settings are enabled on a step.

Regions and portable coordinates: A macro can watch a drawn portion of its
selected monitor. Fixed mouse steps can use absolute screen coordinates,
resolution-scaled Watch percentages, or a percentage inside a saved visible
application window. Safe-preview portable coordinates before live use.

Builder organization: Macro steps can be named, commented, duplicated, and
dragged into a new order without silently changing their branch targets. Add
Section creates a colored divider. Validate Macro checks missing classes,
broken or disabled destinations, unreachable steps, and unbounded loops before
a full run.

Visual macro logic: Flow View draws connected branches and loops. Run-scoped
variables and counters can control true/false routes. Call Macro runs another
project macro and returns, while detection failures can branch to a chosen
recovery step. Exported format-v3 macros bundle called submacros.

Training assistant: Dataset can propose labels from the accepted model, but
you approve every box before saving. Quality Dashboard reports coverage and
near duplicates. New models preserve per-class metrics, notes, confusion
matrices, and training curves for comparison in Model Library.

This is an unsigned experimental build. Windows may warn about software that
does not have an established reputation. Confirm that the ZIP came directly
from the person you trust before opening it.
