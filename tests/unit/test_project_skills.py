"""The project skills under .claude/skills/ (Phase 4).

These exist so a future session inherits the project's conventions automatically. That
only works if they stay well-formed and in sync with the code they describe, so the
structure is checked rather than assumed.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO / ".claude" / "skills"
EXPECTED = {"ethiopic-script", "ocr-eval", "security-review"}


def _skill_dirs() -> list[pathlib.Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def _frontmatter(skill_md: pathlib.Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{skill_md} has no YAML frontmatter"
    fields: dict[str, str] = {}
    key: str | None = None
    for line in match.group(1).splitlines():
        if m := re.match(r"^(\w[\w-]*):\s*(.*)$", line):
            key = m.group(1)
            fields[key] = m.group(2).strip()
        elif key and line.strip():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def test_the_three_required_skills_exist() -> None:
    assert {p.name for p in _skill_dirs()} >= EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_skill_has_a_skill_md(name: str) -> None:
    assert (SKILLS_DIR / name / "SKILL.md").is_file()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_frontmatter_name_matches_directory(name: str) -> None:
    fields = _frontmatter(SKILLS_DIR / name / "SKILL.md")
    assert fields.get("name") == name


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_description_is_substantial_enough_to_trigger(name: str) -> None:
    """The description is the whole triggering mechanism. A terse one under-triggers."""
    description = _frontmatter(SKILLS_DIR / name / "SKILL.md").get("description", "")
    assert len(description) > 200, f"{name}: description too short to trigger reliably"
    assert "use this skill" in description.lower(), f"{name}: no explicit trigger phrasing"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_skill_body_stays_within_the_progressive_disclosure_budget(name: str) -> None:
    """SKILL.md loads whenever the skill triggers; detail belongs in references/."""
    body = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    assert len(body.splitlines()) < 500


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_referenced_files_exist(name: str) -> None:
    """A skill pointing at a file that does not exist is worse than one that does not
    point anywhere."""
    skill_dir = SKILLS_DIR / name
    body = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    # A path may be skill-relative (references/, the skill's own scripts/) or
    # repo-relative (the repo's top-level scripts/). Both are legitimate; resolve either.
    missing = [
        target
        for target in re.findall(r"`(references/[\w./-]+|scripts/[\w./-]+)`", body)
        if not (skill_dir / target).exists() and not (REPO / target).exists()
    ]
    assert not missing, f"{name} references missing files: {missing}"


def test_ethiopic_skill_figures_match_the_code() -> None:
    """The skill quotes 523 codepoints and 35 folded. If the code changes, this fails."""
    from adai.ethiopic.inventory import HOMOPHONE_FAMILIES, VOWEL_ORDERS, ethiopic_codepoints

    body = (SKILLS_DIR / "ethiopic-script" / "SKILL.md").read_text(encoding="utf-8")
    assert str(len(ethiopic_codepoints())) in body
    folded = sum(len(v) - 1 for v in HOMOPHONE_FAMILIES.values()) * VOWEL_ORDERS
    assert str(folded) in body


def test_generated_references_are_in_sync() -> None:
    """Both reference files are generated. Regenerating must be a no-op."""
    scripts = [
        SKILLS_DIR / "ethiopic-script" / "scripts" / "regenerate_inventory.py",
        SKILLS_DIR / "security-review" / "scripts" / "regenerate_checklists.py",
    ]
    targets = [
        SKILLS_DIR / "ethiopic-script" / "references" / "inventory.md",
        SKILLS_DIR / "security-review" / "references" / "checklists.md",
    ]
    before = [t.read_text(encoding="utf-8") for t in targets]
    for script in scripts:
        result = subprocess.run(  # noqa: S603 - fixed paths from this repo, no user input
            [sys.executable, str(script)], capture_output=True, text=True, cwd=REPO, check=False
        )
        assert result.returncode == 0, f"{script.name} failed: {result.stderr}"
    after = [t.read_text(encoding="utf-8") for t in targets]
    assert before == after, "a generated reference is stale; rerun its regenerate script"


def test_security_checklist_covers_every_control() -> None:
    checklist = (SKILLS_DIR / "security-review" / "references" / "checklists.md").read_text(
        encoding="utf-8"
    )
    security = (REPO / "docs" / "SECURITY.md").read_text(encoding="utf-8")
    registered = set(re.findall(r"\*\*(C-\d{2})\*\*", security))
    listed = set(re.findall(r"\|\s*(C-\d{2})\s*\|", checklist))
    assert registered <= listed, f"missing from the checklist: {sorted(registered - listed)}"
