import sys
from pathlib import Path
from backend.api.dependencies.common import _get_session_factory
from backend.services.orchestration.pipeline import run_pipeline

def test():
    session_factory = _get_session_factory()
    db = session_factory()
    try:
        run_pipeline(
            repo_url="https://github.com/pallets/click",
            analysis_id=1,
            repository_id=1,
            db=db,
            repos_dir=Path("data/repos"),
            artifacts_base_dir=Path("data/artifacts"),
            clone_timeout=30,
        )
    finally:
        db.close()

if __name__ == "__main__":
    test()
