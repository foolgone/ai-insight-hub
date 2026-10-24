-- ===================================
-- AI Insight Hub - 数据库初始化脚本
-- 由 docker-compose.yml 挂载到 /docker-entrypoint-initdb.d/init_db.sql
-- 只在数据卷首次初始化时执行（重建需 docker-compose down -v）
-- ===================================

-- pgvector：向量检索（knowledge_base.embedding / cleaned_data.embedding）
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_trgm：中文/模糊检索降级方案（MVP 使用）
-- ⚠️ pgvector/pgvector:pg14 官方镜像不含 zhparser（中文分词扩展），
--    因此 CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser) 在默认镜像下不可用。
--    MVP 阶段统一使用 pg_trgm + ILIKE，zhparser 方案见
--    docs/03-architecture/03-数据库设计.md 附录「自建 PostgreSQL 镜像」。
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID 生成
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid()（PostgreSQL 13+ 内置）

-- 说明：业务表由 Alembic 迁移创建，不在本脚本中建表
--   cd backend && alembic upgrade head
