#!/usr/bin/env python3
"""Validate the portable skill directory contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
NAME = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}, lines
    result: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            return result, lines[index + 1 :]
        key, separator, value = line.partition(":")
        if separator:
            result[key.strip()] = value.strip()
    return {}, lines


def validate_skill(directory: Path) -> list[str]:
    diagnostics: list[str] = []
    skill_file = directory / "SKILL.md"
    label = directory.relative_to(ROOT)
    if not skill_file.is_file():
        return [f"{label}: missing SKILL.md"]

    text = skill_file.read_text()
    metadata, body = parse_frontmatter(text)
    name = metadata.get("name")
    description = metadata.get("description")
    if not name:
        diagnostics.append(f"{label}: frontmatter missing name")
    if not description:
        diagnostics.append(f"{label}: frontmatter missing description")
    if name and name != directory.name:
        diagnostics.append(f"{label}: name must match directory ({directory.name})")
    if name and (len(name) > 64 or not NAME.fullmatch(name)):
        diagnostics.append(f"{label}: name must be lowercase hyphenated and at most 64 characters")
    if len(body) >= 500:
        diagnostics.append(f"{label}: SKILL.md body must be under 500 lines")

    for markdown in directory.rglob("*.md"):
        for target in LINK.findall(markdown.read_text()):
            target = target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("/"):
                continue
            if not (markdown.parent / target).exists():
                diagnostics.append(f"{markdown.relative_to(ROOT)}: missing relative link target {target}")
    return diagnostics


def selected_skills(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir())
    return [Path(path).resolve() for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate portable skill bundles")
    parser.add_argument("--skill", action="append", default=[], metavar="PATH")
    args = parser.parse_args()

    skills = selected_skills(args.skill)
    diagnostics: list[str] = []
    for skill in skills:
        if not skill.is_dir():
            diagnostics.append(f"{skill}: skill directory does not exist")
            continue
        diagnostics.extend(validate_skill(skill))
    if diagnostics:
        print("\n".join(diagnostics))
        return 1
    print(f"validated: {len(skills)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
