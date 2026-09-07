"""Fail fast when public-release metadata or bundled examples disagree."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def app_version() -> str:
    text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("app/__init__.py does not define __version__.")
    return match.group(1)


def validate(tag: str = "") -> list[str]:
    version = app_version()
    errors: list[str] = []
    required = (
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "SOURCE_OFFER.txt",
        "SECURITY.md",
        "SUPPORT.md",
        "CONTRIBUTING.md",
        "RELEASE_NOTES.md",
        "docs/PRIVACY.md",
        "docs/USER_GUIDE.md",
        "docs/RELEASE_CHECKLIST.md",
        ".github/workflows/tests.yml",
        ".github/workflows/codeql.yml",
        ".github/workflows/windows-release.yml",
    )
    for relative in required:
        if not (PROJECT_ROOT / relative).is_file():
            errors.append(f"Missing required release file: {relative}")

    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text[:300]:
        errors.append("LICENSE is not the GNU Affero General Public License.")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    source_offer = (PROJECT_ROOT / "SOURCE_OFFER.txt").read_text(encoding="utf-8")
    portable = (PROJECT_ROOT / "PORTABLE_README.txt").read_text(encoding="utf-8")
    for name, content in (
        ("README.md", readme),
        ("SOURCE_OFFER.txt", source_offer),
        ("PORTABLE_README.txt", portable),
    ):
        if version not in content:
            errors.append(f"{name} does not mention version {version}.")
    if f"## [{version}]" not in changelog:
        errors.append(f"CHANGELOG.md has no {version} section.")
    if f"tree/v{version}" not in source_offer:
        errors.append("SOURCE_OFFER.txt does not point to the matching source tag.")
    if tag and tag != f"v{version}":
        errors.append(f"Tag {tag!r} does not match application version v{version}.")

    from app.automation.macro_io import import_macro_file

    for example in sorted((PROJECT_ROOT / "examples").glob("*.vmsmacro.json")):
        try:
            import_macro_file(example)
        except Exception as exc:
            errors.append(f"Invalid example {example.name}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    errors = validate(args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Vision Macro Studio v{app_version()} release metadata: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
