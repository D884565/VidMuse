"""调试数据库查询"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from backend.v1.app.config.config import settings
from backend.v1.app.models.inspiration_template import Factor, Strategy, InspirationTemplate, TemplateFactorRelation

async def main():
    # 创建数据库引擎
    engine = create_async_engine(settings.db_url, echo=True)

    async with AsyncSession(engine) as session:
        print("=== 查询数据库 ===")

        # 查询因子数量
        result = await session.execute(text("SELECT COUNT(*) FROM factors"))
        factor_count = result.scalar_one()
        print(f"factors表记录数: {factor_count}")

        # 查询策略数量
        result = await session.execute(text("SELECT COUNT(*) FROM strategies"))
        strategy_count = result.scalar_one()
        print(f"strategies表记录数: {strategy_count}")

        # 查询模板数量
        result = await session.execute(text("SELECT COUNT(*) FROM inspiration_templates"))
        template_count = result.scalar_one()
        print(f"inspiration_templates表记录数: {template_count}")

        # 查询关联关系数量
        result = await session.execute(text("SELECT COUNT(*) FROM template_factor_relations"))
        relation_count = result.scalar_one()
        print(f"template_factor_relations表记录数: {relation_count}")

        print("\n=== 查看部分数据 ===")

        # 查看前5个因子
        if factor_count > 0:
            result = await session.execute(text("SELECT * FROM factors LIMIT 5"))
            print("\n前5个因子:")
            for row in result:
                print(f"  ID: {row.id}, factor_id: {row.factor_id}, name: {row.name}, is_deleted: {row.is_deleted}")

        # 查看前5个策略
        if strategy_count > 0:
            result = await session.execute(text("SELECT * FROM strategies LIMIT 5"))
            print("\n前5个策略:")
            for row in result:
                print(f"  ID: {row.id}, strategy_id: {row.strategy_id}, name: {row.name}, is_deleted: {row.is_deleted}")

        # 查看前5个模板
        if template_count > 0:
            result = await session.execute(text("SELECT * FROM inspiration_templates LIMIT 5"))
            print("\n前5个模板:")
            for row in result:
                print(f"  ID: {row.id}, template_id: {row.template_id}, strategy_id: {row.strategy_id}, name: {row.name}, is_deleted: {row.is_deleted}")

        # 查看前5个关联关系
        if relation_count > 0:
            result = await session.execute(text("SELECT * FROM template_factor_relations LIMIT 5"))
            print("\n前5个关联关系:")
            for row in result:
                print(f"  ID: {row.id}, template_id: {row.template_id}, factor_id: {row.factor_id}, usage_type: {row.factor_usage_type}")

if __name__ == "__main__":
    asyncio.run(main())
