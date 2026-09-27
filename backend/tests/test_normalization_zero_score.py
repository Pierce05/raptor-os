from app import models
from app.normalization import run_normalization


def test_unscored_project_appears_flagged(db_session, seeded):
    """
    A second project in the same event that no judge has scored yet
    must still show up in NormalizationRun.results -- flagged
    insufficient_data=True with null rank/score fields -- rather than
    being silently dropped from results/CSV/rankings.
    """
    unscored_project = models.Project(
        team_id=seeded["project"].team_id,
        title="Unreviewed Project",
        status="submitted",
    )
    db_session.add(unscored_project)
    db_session.commit()

    run = run_normalization(db_session, seeded["event"].id)
    db_session.commit()

    scored_id = seeded["project"].id
    unscored_id = unscored_project.id

    assert scored_id in run.results
    assert unscored_id in run.results

    assert run.results[scored_id]["insufficient_data"] is False
    assert run.results[scored_id]["final_rank"] == 1

    unscored_result = run.results[unscored_id]
    assert unscored_result["insufficient_data"] is True
    assert unscored_result["final_rank"] is None
    assert unscored_result["raw_average"] is None
