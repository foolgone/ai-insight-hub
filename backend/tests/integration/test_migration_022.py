"""C2：migration 022 结构、回填分支、downgrade 恢复与约束。"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
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
MIGRATION_PATH = (
    BACKEND_DIR
    / "migrations"
    / "versions"
    / "20261119_1800_f3a9c2d7e1b4_022_m1c_dual_faithfulness.py"
)
REV_021 = "d4e8b1c6f902"
REV_022 = "f3a9c2d7e1b4"


# --------------------------------------------------------------------------- 基础工具


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("+asyncpg", "")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _migration_module():
    spec = importlib.util.spec_from_file_location("migration_022", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fetch(sql: str, **params: object) -> list[tuple[object, ...]]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql), params).all())
    finally:
        engine.dispose()


def _scalar(sql: str, **params: object):
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params).scalar()
    finally:
        engine.dispose()


def _seed_dataset(session: Session, item_count: int):
    user = UserFactory(email=f"migration022-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.flush()

    dataset = QaDataset(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=f"migration022-{uuid.uuid4().hex[:8]}",
        source_type="doc",
    )
    session.add(dataset)
    session.flush()

    version = QaDatasetVersion(
        tenant_id=user.tenant_id,
        dataset_id=dataset.id,
        version=1,
        status="published",
        item_count=item_count,
        checksum="migration-022",
    )
    session.add(version)
    session.flush()

    items = [
        QaDatasetItem(
            tenant_id=user.tenant_id,
            version_id=version.id,
            item_key=f"I{index}",
            query=f"query-{index}",
            gold_answer="answer",
            split="test",
        )
        for index in range(1, item_count + 1)
    ]
    session.add_all(items)
    session.flush()
    return user, dataset, version, items


def _create_run(
    session: Session,
    *,
    user,
    dataset,
    version,
    total_items: int,
    completed_items: int,
) -> RagEvaluationRun:
    run = RagEvaluationRun(
        tenant_id=user.tenant_id,
        user_id=user.id,
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        dataset_version_id=version.id,
        execution_mode="query",
        adapter="mock",
        total_items=total_items,
        completed_items=completed_items,
        status="completed",
    )
    session.add(run)
    session.flush()
    return run


def _add_result(
    session: Session,
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    metric_name: str,
    metric_version: str,
    status: str,
    invalid_reason: str | None = None,
    skipped_reason: str | None = None,
    score: float | None = None,
    derived_from_result_id: uuid.UUID | None = None,
) -> RagEvaluationResult:
    row = RagEvaluationResult(
        tenant_id=run.tenant_id,
        run_id=run.id,
        dataset_item_id=item.id,
        metric_name=metric_name,
        metric_version=metric_version,
        status=status,
        invalid_reason=invalid_reason,
        skipped_reason=skipped_reason,
        score=score,
        derived_from_result_id=derived_from_result_id,
    )
    session.add(row)
    session.flush()
    return row


def _cleanup(
    engine,
    *,
    run_ids: list[uuid.UUID],
    dataset_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> None:
    with engine.begin() as conn:
        for run_id in run_ids:
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


# --------------------------------------------------------------------------- 结构


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


# --------------------------------------------------------------------------- 历史回填 / backup


def test_c2_backfill_buckets_backup_and_versions() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(_sync_url())
    run_ids: list[uuid.UUID] = []
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user, dataset, version, items = _seed_dataset(session, 8)
            run = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=8,
                completed_items=6,
            )
            run_no_results = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=3,
                completed_items=3,
            )

            # I1 evaluated；额外 v1 行用于验证版本不被迁移重写
            _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="evaluated",
                score=1.0,
            )
            _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="answer_relevancy",
                metric_version="v1",
                status="evaluated",
                score=0.9,
            )

            # I2 skipped
            _add_result(
                session,
                run=run,
                item=items[1],
                metric_name="faithfulness",
                metric_version="v2",
                status="skipped",
                skipped_reason="no_scorable_claims",
            )

            # I3 execution failed
            _add_result(
                session,
                run=run,
                item=items[2],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
            )

            # I4 evaluated + skipped 同一 Item，evaluated 优先
            _add_result(
                session,
                run=run,
                item=items[3],
                metric_name="faithfulness",
                metric_version="v2",
                status="evaluated",
                score=1.0,
            )
            _add_result(
                session,
                run=run,
                item=items[3],
                metric_name="answer_correctness",
                metric_version="v2",
                status="skipped",
                skipped_reason="no_scorable_claims",
            )

            # I5：无任何 result row（items[4]）

            # I6：partial item（只有一条 skipped row）
            _add_result(
                session,
                run=run,
                item=items[5],
                metric_name="faithfulness",
                metric_version="v2",
                status="skipped",
                skipped_reason="no_scorable_claims",
            )

            # I7：failed + evaluated 同一 Item，failed 优先
            _add_result(
                session,
                run=run,
                item=items[6],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
            )
            _add_result(
                session,
                run=run,
                item=items[6],
                metric_name="answer_correctness",
                metric_version="v2",
                status="evaluated",
                score=0.8,
            )

            # I8 skipped
            _add_result(
                session,
                run=run,
                item=items[7],
                metric_name="faithfulness",
                metric_version="v2",
                status="skipped",
                skipped_reason="no_scorable_claims",
            )

            session.commit()
            run_ids = [run.id, run_no_results.id]
            dataset_id = dataset.id
            user_id = user.id
        engine.dispose()

        # 旧 completed_items 备份并降级
        command.downgrade(config, REV_021)
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_ids[0])
            == 6
        )
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_ids[1])
            == 3
        )

        # 升级回填
        command.upgrade(config, "head")
        with Session(engine) as session:
            run = session.get(RagEvaluationRun, run_ids[0])
            assert run is not None
            assert run.evaluated_items == 2
            assert run.invalid_items == 0
            assert run.failed_items == 2
            assert run.skipped_items == 3
            assert run.unprocessed_items == 1
            assert run.completed_items == 2
            assert (
                run.evaluated_items
                + run.invalid_items
                + run.failed_items
                + run.skipped_items
                + run.unprocessed_items
                == 8
            )

            run_no_results = session.get(RagEvaluationRun, run_ids[1])
            assert run_no_results is not None
            assert run_no_results.evaluated_items == 0
            assert run_no_results.invalid_items == 0
            assert run_no_results.failed_items == 0
            assert run_no_results.skipped_items == 0
            assert run_no_results.unprocessed_items == 3
            assert run_no_results.completed_items == 0

            versions = set(
                session.execute(
                    select(RagEvaluationResult.metric_version).where(
                        RagEvaluationResult.run_id == run_ids[0]
                    )
                )
                .scalars()
                .all()
            )
            assert versions == {"v1", "v2"}

        # 再次 downgrade：completed 从 backup 恢复旧值
        engine.dispose()
        command.downgrade(config, REV_021)
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_ids[0])
            == 6
        )
        assert (
            _scalar("SELECT completed_items FROM rag_evaluation_runs WHERE id = :id", id=run_ids[1])
            == 3
        )
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        _cleanup(engine, run_ids=run_ids, dataset_id=dataset_id, user_id=user_id)


# --------------------------------------------------------------------------- B 方案回填


def test_c2_backfill_classifies_b_as_invalid() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    migration = _migration_module()

    engine = create_engine(_sync_url())
    run_ids: list[uuid.UUID] = []
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user, dataset, version, items = _seed_dataset(session, 5)
            run = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=5,
                completed_items=0,
            )

            # I1：A invalid
            _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="invalid",
                invalid_reason="contract_violation",
            )
            # I2：B invalid（failed + invalid_reason）
            _add_result(
                session,
                run=run,
                item=items[1],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
                invalid_reason="contract_violation",
            )
            # I3：execution failed（无 reason）
            _add_result(
                session,
                run=run,
                item=items[2],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
            )
            # I4：invalid A + evaluated，invalid 优先
            _add_result(
                session,
                run=run,
                item=items[3],
                metric_name="faithfulness",
                metric_version="v2",
                status="evaluated",
                score=1.0,
            )
            _add_result(
                session,
                run=run,
                item=items[3],
                metric_name="answer_correctness",
                metric_version="v2",
                status="invalid",
                invalid_reason="contract_violation",
            )
            # I5：execution failed + B invalid，failed 优先；B 行仍保留
            _add_result(
                session,
                run=run,
                item=items[4],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
            )
            _add_result(
                session,
                run=run,
                item=items[4],
                metric_name="answer_correctness",
                metric_version="v2",
                status="failed",
                invalid_reason="contract_violation",
            )
            session.commit()
            run_ids = [run.id]
            dataset_id = dataset.id
            user_id = user.id
        engine.dispose()

        # 在事务内执行 migration 的真实回填 SQL，断言后回滚，避免影响其他 Run。
        with engine.connect() as conn:
            transaction = conn.begin()
            migration._backfill(conn)
            row = conn.execute(
                text(
                    "SELECT evaluated_items, invalid_items, failed_items, "
                    "skipped_items, unprocessed_items, completed_items "
                    "FROM rag_evaluation_runs WHERE id = :id"
                ),
                {"id": run_ids[0]},
            ).one()
            assert tuple(row) == (0, 3, 2, 0, 0, 0)
            b_rows = conn.execute(
                text(
                    "SELECT count(*) FROM rag_evaluation_results "
                    "WHERE run_id = :id AND status = 'failed' "
                    "AND invalid_reason IS NOT NULL"
                ),
                {"id": run_ids[0]},
            ).scalar_one()
            assert b_rows == 2
            transaction.rollback()
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        _cleanup(engine, run_ids=run_ids, dataset_id=dataset_id, user_id=user_id)


# --------------------------------------------------------------------------- downgrade 拒绝


def test_c2_downgrade_rejects_a_b_and_strict() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(_sync_url())
    run_ids: list[uuid.UUID] = []
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user, dataset, version, items = _seed_dataset(session, 1)
            run = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=1,
                completed_items=1,
            )
            row = _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="invalid",
                invalid_reason="contract_violation",
            )
            session.commit()
            run_ids = [run.id]
            dataset_id = dataset.id
            user_id = user.id
            row_id = row.id
        engine.dispose()

        # A invalid
        with pytest.raises(RuntimeError, match="invalid/faithfulness_strict"):
            command.downgrade(config, REV_021)

        # B invalid：failed + invalid_reason
        with Session(engine) as session:
            row = session.get(RagEvaluationResult, row_id)
            assert row is not None
            row.status = "failed"
            row.invalid_reason = "contract_violation"
            session.commit()
        engine.dispose()
        with pytest.raises(RuntimeError, match="invalid/faithfulness_strict"):
            command.downgrade(config, REV_021)

        # strict 行
        with Session(engine) as session:
            row = session.get(RagEvaluationResult, row_id)
            assert row is not None
            row.status = "evaluated"
            row.invalid_reason = None
            row.metric_name = "faithfulness_strict"
            row.score = 1.0
            session.commit()
        engine.dispose()
        with pytest.raises(RuntimeError, match="invalid/faithfulness_strict"):
            command.downgrade(config, REV_021)
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        _cleanup(engine, run_ids=run_ids, dataset_id=dataset_id, user_id=user_id)


# --------------------------------------------------------------------------- CASCADE


def test_c2_derived_from_result_cascade() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(_sync_url())
    run_ids: list[uuid.UUID] = []
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user, dataset, version, items = _seed_dataset(session, 1)
            run = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=1,
                completed_items=1,
            )
            coverage = _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="evaluated",
                score=1.0,
            )
            strict = _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness_strict",
                metric_version="v2",
                status="evaluated",
                score=1.0,
                derived_from_result_id=coverage.id,
            )
            session.commit()
            run_ids = [run.id]
            dataset_id = dataset.id
            user_id = user.id
            coverage_id = coverage.id
            strict_id = strict.id
        engine.dispose()

        with Session(engine) as session:
            coverage = session.get(RagEvaluationResult, coverage_id)
            assert coverage is not None
            session.delete(coverage)
            session.commit()

        assert (
            _scalar("SELECT count(*) FROM rag_evaluation_results WHERE id = :id", id=strict_id) == 0
        )
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        _cleanup(engine, run_ids=run_ids, dataset_id=dataset_id, user_id=user_id)


# --------------------------------------------------------------------------- invalid 约束


def test_c2_invalid_reason_constraints() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(_sync_url())
    run_ids: list[uuid.UUID] = []
    dataset_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    try:
        with Session(engine) as session:
            user, dataset, version, items = _seed_dataset(session, 1)
            run = _create_run(
                session,
                user=user,
                dataset=dataset,
                version=version,
                total_items=1,
                completed_items=0,
            )

            nested = session.begin_nested()
            session.add(
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=items[0].id,
                    metric_name="faithfulness",
                    metric_version="v2",
                    status="invalid",
                    invalid_reason=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
            nested.rollback()

            invalid_with_reason = _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="invalid",
                invalid_reason="contract_violation",
            )
            session.delete(invalid_with_reason)
            session.flush()

            failed_with_reason = _add_result(
                session,
                run=run,
                item=items[0],
                metric_name="faithfulness",
                metric_version="v2",
                status="failed",
                invalid_reason="contract_violation",
            )
            session.delete(failed_with_reason)
            session.commit()
            run_ids = [run.id]
            dataset_id = dataset.id
            user_id = user.id
    finally:
        engine.dispose()
        command.upgrade(config, "head")
        _cleanup(engine, run_ids=run_ids, dataset_id=dataset_id, user_id=user_id)
