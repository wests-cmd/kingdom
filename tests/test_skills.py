import pytest
from backend.storage.db import Database
from backend.skills.repository import SkillRepository
from backend.skills.skill_engine import SkillEngine

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    test_db_path = tmp_path / "test_skills.db"
    db_inst = Database(db_path=test_db_path)
    repo = SkillRepository(database=db_inst)
    engine = SkillEngine(repository=repo)
    yield (repo, engine)

def test_skill_repository_and_engine(setup_test_db):
    repo, engine = setup_test_db

    skills = repo.list_skills()
    assert len(skills) >= 1

    sec_skill = repo.get_skill("skill-code-review")
    assert sec_skill is not None
    assert sec_skill["name"] == "Automated Code Review"

    resolution = engine.resolve_dependencies("skill-code-review")
    assert "required_departments" in resolution
    assert "Development" in resolution["required_departments"]
    assert resolution["readiness_status"] == "READY"

def test_bundle_creation(setup_test_db):
    repo, engine = setup_test_db
    bundle = engine.create_bundle(
        name="Test Security Bundle",
        description="Bundle for security testing",
        skill_ids=["skill-code-review", "skill-market-research"]
    )
    assert bundle["id"].startswith("bundle-")
    assert len(bundle["skill_ids"]) == 2

    bundles = engine.list_bundles()
    assert any(b["id"] == bundle["id"] for b in bundles)
