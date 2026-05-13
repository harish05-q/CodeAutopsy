from backend.api.dependencies.common import _get_session_factory
from backend.models.database import Analysis, AnalysisStatus

def test():
    db = _get_session_factory()()
    analysis = (
        db.query(Analysis)
        .filter(Analysis.status == AnalysisStatus.COMPLETED)
        .order_by(Analysis.id.desc())
        .first()
    )
    if analysis:
        print(f"Found completed analysis: {analysis.id} for repo: {analysis.repository_id}")
    else:
        print("No completed analysis found.")
    db.close()

if __name__ == "__main__":
    test()
