"""C2：migration 022 结构、回填与 downgrade 恢复。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    QaDataset,
    QaDatasetItem,
    QaDatasetVersion,
    RagEvaluationResult,
    RagEvaluationRun,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
REV_021 = "d4e8b1c6f902"
REV_022 = "f3a9c2d7e1b4"


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("+asyncpg", "")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _scalar(sql: str, **params: object):
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params).scalar()
    finally:
        engine.dispose()


def test_c2_schema_at_head() -> None:
    result_columns = {
        row[0]
        for row in _fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'rag_evaluation_results'
            """
        )
    }
    run_columns = {
        row[0]
        for row in _fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'rag_evaluation_runs'
            """
        )
    }
    assert {"invalid_reason", "derived_from_result_id"} <= result_columns
    assert {"evaluated_items", "invalid_items", "unprocessed_items"} <= run_columns

    constraint_defs = {
        row[0]: row[1]
        for row in _fetch(
            """
            SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid IN (
                'rag_evaluation_results'::regclass,
                'rag_evaluation_runs'::regclass
            )
            """
        )
    }
    joined = "\n".join(str(value) for value in constraint_defs.values())
    assert any(name.endswith("rag_eval_result_status_m1c") for name in constraint_defs)
    assert "invalid_reason IS NOT NULL" in joined
    assert any(name.endswith("rag_eval_result_invalid_reason_status") for name in constraint_defs)
    assert "fk_rag_evaluation_results_derived_from" in constraint_defs

    indexes = {
        row[0] for row in _fetch("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    }
    assert "idx_rag_evaluation_results_derived_from" in indexes
    assert _scalar("SELECT to_regclass('rag_evaluation_runs_022_completed_backup')") is not None


def test_c2_upgrade_backfill_and_downgrade_restore() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(_sync_url())
    run_id: uuid.UUID | None = None
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user = UserFactory(email=f"migration022-{uuid.uuid4().hex[:8]}@example.com")
            session.add(user)
            session.flush()

            dataset = QaDataset(
                user_id=user.id,
                name=f"migration022-{uuid.uuid4().hex[:8]}",
                source_type="doc",
            )
            session.add(dataset)
            session.flush()

            version = QaDatasetVersion(
                dataset_id=dataset.id,
                version=1,
                status="published",
                item_count=3,
                checksum="migration-022",
            )
            session.add(version)
            session.flush()

            items = [
                QaDatasetItem(
                    version_id=version.id,
                    item_key=f"I{index}",
                    query=f"query-{index}",
                    gold_answer="answer",
                    split="test",
                )
                for index in (1, 2, 3)
            ]
            session.add_all(items)
            session.flush()

            run = RagEvaluationRun(
                user_id=user.id,
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                dataset_version_id=version.id,
                execution_mode="query",
                adapter="mock",
                total_items=3,
                # 旧语义：evaluated 2 + skipped 1 都算 completed
                completed_items=3,
                status="completed",
            )
            session.add(run)
            session.flush()

            results = [
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=items[0].id,
                    metric_name="faithfulness",
                    metric_version="v2",
                    status="evaluated",
                    score=1.0,
                ),
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=items[1].id,
                    metric_name="faithfulness",
                    metric_version="v2",
                    status="evaluated",
                    score=0.5,
                ),
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=items[2].id,
                    metric_name="faithfulness",
                    metric_version="v2",
                    status="skipped",
                    skipped_reason="no_scorable_claims",
                ),
            ]
            session.add_all(results)
            session.commit()

            # invalid 必须有 reason；failed + reason 允许。
            nested = session.begin_nested()
            session.add(
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=items[0].id,
                    metric_name="answer_correctness",
                    metric_version="v2",
                    status="invalid",
                    invalid_reason=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
            nested.rollback()

            invalid_with_reason = RagEvaluationResult(
                run_id=run.id,
                dataset_item_id=items[0].id,
                metric_name="answer_correctness",
                metric_version="v2",
                status="invalid",
                invalid_reason="contract_violation",
            )
            session.add(invalid_with_reason)
            session.flush()
            session.delete(invalid_with_reason)
            session.flush()

            failed_with_reason = RagEvaluationResult(
                run_id=run.id,
                dataset_item_id=items[0].id,
                metric_name="answer_correctness",
                metric_version="v2",
                status="failed",
                invalid_reason="contract_violation",
            )
            session.add(failed_with_reason)
            session.flush()
            session.delete(failed_with_reason)
            session.commit()

            run_id = run.id
            dataset_id = dataset.id
            user_id = user.id
        engine.dispose()

        # downgrade 022：备份旧 completed_items，恢复旧列集合。
        command.downgrade(config, REV_021)
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_id)
            == 3
        )
        assert _scalar("SELECT to_regclass('rag_evaluation_runs_022_completed_backup')") is None

        # upgrade 022：按 Item 优先级回填，completed=evaluated。
        command.upgrade(config, "head")
        with Session(engine) as session:
            run = session.get(RagEvaluationRun, run_id)
            assert run is not None
            assert run.evaluated_items == 2
            assert run.invalid_items == 0
            assert run.failed_items == 0
            assert run.skipped_items == 1
            assert run.unprocessed_items == 0
            assert run.completed_items == 2

        # 再 downgrade：completed 从 backup 恢复为旧值。
        engine.dispose()
        command.downgrade(config, REV_021)
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_id)
            == 3
        )
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        cleanup_engine = create_engine(_sync_url())
        try:
            with cleanup_engine.begin() as conn:
                if run_id is not None:
                    conn.execute(
                        text("DELETE FROM rag_evaluation_results WHERE run_id = :id"),
                        {"id": run_id},
                    )
                    conn.execute(
                        text("DELETE FROM rag_evaluation_runs WHERE id = :id"),
                        {"id": run_id},
                    )
                if dataset_id is not None:
                    conn.execute(
                        text("DELETE FROM qa_datasets WHERE id = :id"),
                        {"id": dataset_id},
                    )
                if user_id is not None:
                    conn.execute(
                        text("DELETE FROM users WHERE id = :id"),
                        {"id": user_id},
                    )
        finally:
            cleanup_engine.dispose()


def _fetch(sql: str) -> list[tuple[object, ...]]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql)).all())
    finally:
        engine.dispose()
