# Privacy and local data

Vision Macro Studio is designed as a local desktop application.

## Stored locally

General settings are stored under the current Windows account's application
data folder. New project storage defaults to:

`Documents\Vision Macro Studio Projects`

Each project folder contains its own captures, crops, dataset exports, trained
models, macros, logs, metadata, and training reports. Paths are chosen at
runtime and are not hard-coded to the developer's computer.

## Network activity

Vision Macro Studio has no telemetry, advertising, cloud account, automatic
upload, or automatic update check. It does not upload captures, labels, models,
macros, or logs.

Network access can still occur outside the application in these cases:

- source setup installs Python packages from the configured package index;
- a first training run may ask Ultralytics to obtain a selected pretrained
  model if it is not already cached;
- Help links open GitHub or upstream documentation in the default browser.

## Captures and models

A screen capture can contain messages, names, account details, or anything else
visible in the selected screen region. Trained models and class names can also
reveal the purpose of a project. Review project exports before sharing them.

## Diagnostic packages

The built-in diagnostic exporter contains a general runtime report, safe
settings, class and accepted-model metadata, redacted macro structure, and the
last 100 visible log lines. It does not include screenshots, labels, project
paths, model files, settings paths, typed text, or window titles.

Redaction is a safety aid rather than a guarantee. Always inspect a diagnostic
ZIP before posting it publicly.
