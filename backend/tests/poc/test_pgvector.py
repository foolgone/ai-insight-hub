"""B-102：pgvector 384 维 + HNSW 检索验证。

覆盖两部分：
1. 质量：真实 embedding（MiniLM 384 维）下语义近邻相似度 > 50%；
2. 性能：1 万条 384 维向量 + HNSW，单次检索 < 100ms。

需要本地 PostgreSQL 14 + pgvector（``DATABASE_URL``）；embedding 模型不可用时质量用例 skip。
"""
from __future__ import annotations

import random
import time

import asyncpg
import pytest

from tests.poc.conftest import database_dsn, skip_without_embedding_model

pytestmark = [pytest.mark.slow, pytest.mark.integration]

EMBEDDING_DIM = 384
HNSW_DDL = (
    "CREATE INDEX {idx} ON {table} USING hnsw (embedding vector_cosine_ops) "
    "WITH (m=16, ef_construction=64)"
)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


async def _create_table(conn: asyncpg.Connection, table: str) -> None:
    await conn.execute(f"DROP TABLE IF EXISTS {table}")
    await conn.execute(
        f"""
        CREATE TABLE {table} (
            id BIGSERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            embedding VECTOR({EMBEDDING_DIM})
        )
        """
    )


async def test_extension_and_vector_dimension() -> None:
    conn = await asyncpg.connect(database_dsn())
    try:
        ext = await conn.fetchval("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        assert ext == "vector", "数据库未安装 pgvector 扩展"

        await _create_table(conn, "poc_embeddings_dim")
        await conn.execute(
            "INSERT INTO poc_embeddings_dim (content, embedding) VALUES ($1, $2::vector)",
            "dim check",
            _vector_literal([0.01] * EMBEDDING_DIM),
        )
        dims = await conn.fetchval("SELECT vector_dims(embedding) FROM poc_embeddings_dim LIMIT 1")
        assert dims == EMBEDDING_DIM
        print(f"\n[POC-2] pgvector 可用，向量维度 = {dims}")
    finally:
        await conn.execute("DROP TABLE IF EXISTS poc_embeddings_dim")
        await conn.close()


async def test_semantic_search_quality() -> None:
    """真实 embedding 的语义检索：最近邻相似度 > 0.5。"""
    skip_without_embedding_model()
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception as exc:  # pragma: no cover - 依赖模型下载/本地缓存
        pytest.skip(f"embedding 模型不可用：{exc}")

    texts = [
        "iPhone 14 的价格是 5999 元",
        "退货需要在 7 天内申请",
        "支持花呗分期付款",
    ]
    query = "iPhone 14 多少钱"

    embeddings = model.encode(texts + [query]).tolist()
    rows = [(text, _vector_literal(vec)) for text, vec in zip(texts, embeddings[:3])]
    query_literal = _vector_literal(embeddings[-1])

    conn = await asyncpg.connect(database_dsn())
    try:
        await _create_table(conn, "poc_embeddings_quality")
        await conn.executemany(
            "INSERT INTO poc_embeddings_quality (content, embedding) VALUES ($1, $2::vector)",
            rows,
        )
        results = await conn.fetch(
            """
            SELECT content, 1 - (embedding <=> $1::vector) AS similarity
            FROM poc_embeddings_quality
            ORDER BY embedding <=> $1::vector
            LIMIT 3
            """,
            query_literal,
        )
        assert results, "检索无结果"
        top = results[0]
        assert top["content"] == texts[0], f"最近邻错误：{top['content']}"
        assert top["similarity"] > 0.5, f"相似度过低：{top['similarity']:.3f}"
        print("\n[POC-2] 语义检索 Top1=" f"{top['content']} similarity={top['similarity']:.4f}")
    finally:
        await conn.execute("DROP TABLE IF EXISTS poc_embeddings_quality")
        await conn.close()


async def test_hnsw_search_performance_10k() -> None:
    """1 万条 384 维向量 + HNSW：单次检索 < 100ms。"""
    rows = 10_000
    conn = await asyncpg.connect(database_dsn())
    try:
        await _create_table(conn, "poc_embeddings_perf")
        started = time.perf_counter()
        await conn.execute(
            f"""
            INSERT INTO poc_embeddings_perf (content, embedding)
            SELECT 'synthetic ' || i,
                   (
                       '[' || string_agg(random()::text, ',') || ']'
                   )::vector({EMBEDDING_DIM})
            FROM generate_series(1, {rows}) AS i,
                 generate_series(1, {EMBEDDING_DIM}) AS j
            GROUP BY i
            """
        )
        insert_ms = (time.perf_counter() - started) * 1000
        await conn.execute(HNSW_DDL.format(idx="idx_poc_perf_hnsw", table="poc_embeddings_perf"))
        await conn.execute("SET hnsw.ef_search = 40")

        rng = random.Random(42)
        query = _vector_literal([rng.random() for _ in range(EMBEDDING_DIM)])
        timings: list[float] = []
        for _ in range(3):
            started = time.perf_counter()
            found = await conn.fetch(
                """
                SELECT id FROM poc_embeddings_perf
                ORDER BY embedding <=> $1::vector
                LIMIT 10
                """,
                query,
            )
            timings.append((time.perf_counter() - started) * 1000)
            assert len(found) == 10

        best = min(timings)
        print(
            f"\n[POC-2] 10k 向量 HNSW：插入 {insert_ms:.0f}ms，"
            f"检索 {best:.1f}ms（3 次：{[round(t, 1) for t in timings]}）"
        )
        assert best < 100, f"检索耗时 {best:.1f}ms 超过 100ms"
    finally:
        await conn.execute("DROP TABLE IF EXISTS poc_embeddings_perf")
        await conn.close()
