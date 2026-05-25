"""Alembic 环境配置"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 导入所有模型以便 Alembic 能够检测到
from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.user import User
from backend.v1.app.models.product import Product
from backend.v1.app.models.merge_task import MergeTask
from backend.store.database.async_database import Base

# Alembic Config 对象
config = context.config

# 设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
