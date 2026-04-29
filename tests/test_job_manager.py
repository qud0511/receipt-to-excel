import pytest
from app.core.job_manager import InMemoryJobManager


@pytest.fixture
def mgr():
    return InMemoryJobManager()


async def test_create_and_get(mgr):
    await mgr.create("j1", template_id="t1", total=5)
    job = await mgr.get("j1")
    assert job.job_id == "j1"
    assert job.status == "pending"
    assert job.total == 5
    assert job.done == 0


async def test_update_progress(mgr):
    await mgr.create("j1", template_id="t1", total=3)
    await mgr.update("j1", done=1, current_file="a.jpg")
    job = await mgr.get("j1")
    assert job.status == "processing"
    assert job.done == 1
    assert job.current_file == "a.jpg"


async def test_fail_file_accumulates(mgr):
    await mgr.create("j1", template_id="t1", total=3)
    await mgr.fail_file("j1", "bad.jpg")
    await mgr.fail_file("j1", "bad2.jpg")
    job = await mgr.get("j1")
    assert "bad.jpg" in job.failed_files
    assert "bad2.jpg" in job.failed_files


async def test_complete(mgr):
    await mgr.create("j1", template_id="t1", total=2)
    await mgr.complete("j1", download_url="/jobs/j1/result")
    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.download_url == "/jobs/j1/result"


async def test_fail_job(mgr):
    await mgr.create("j1", template_id="t1", total=1)
    await mgr.fail("j1", error="Ollama timeout")
    job = await mgr.get("j1")
    assert job.status == "failed"
    assert job.error == "Ollama timeout"


async def test_get_nonexistent_raises(mgr):
    with pytest.raises(KeyError):
        await mgr.get("nonexistent")
