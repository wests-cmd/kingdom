"""Model capacity must retain conservative limits across incomplete inventories."""
import asyncio
import pytest
from backend.models.capacity import ModelCapacity


def profile(ident, endpoint, limit=1):
    return {"id": ident, "endpoint": endpoint, "max_parallel": limit}


def test_missing_inventory_candidate_remains_bounded():
    async def run():
        cap = ModelCapacity()
        candidate = profile("a", "http://localhost:1234")
        other = profile("b", "http://localhost:5678")
        async with cap.acquire([candidate], server_profiles=[other]) as selected:
            assert selected == candidate
            with pytest.raises(TimeoutError):
                async with cap.acquire([candidate], wait_seconds=0, server_profiles=[other]):
                    pytest.fail("Second inference must not start")
        assert cap.status([candidate])[0]["active"] == 0
    asyncio.run(run())


def test_shared_host_uses_most_conservative_limit():
    async def run():
        cap = ModelCapacity()
        candidate = profile("a", "http://localhost:1234", 4)
        other = profile("b", "http://localhost:1234", 1)
        async with cap.acquire([candidate], server_profiles=[other]):
            with pytest.raises(TimeoutError):
                async with cap.acquire([candidate], wait_seconds=0, server_profiles=[other]):
                    pytest.fail("Shared server limit must apply")
    asyncio.run(run())


@pytest.mark.parametrize("limit", [0, 5, True, "2"])
def test_invalid_limit_is_rejected(limit):
    async def run():
        cap = ModelCapacity()
        with pytest.raises(ValueError, match="concurrency limit"):
            async with cap.acquire([profile("a", "http://localhost:1234", limit)]):
                pytest.fail("Invalid capacity must not be admitted")
    asyncio.run(run())
