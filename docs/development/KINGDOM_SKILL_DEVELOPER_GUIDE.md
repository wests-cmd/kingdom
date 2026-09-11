# Kingdom Skill Developer Guide

## Creating a Skill Package

1. Construct a typed `Skill` manifest (`backend/skills/models.py`).
2. Declare required capabilities and required skills.
3. Test skill using `SkillTestHarness` (`backend/skills/test_harness.py`).
4. Install via `SkillInstaller` (`backend/skills/installer.py`).
