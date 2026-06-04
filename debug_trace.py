"""调试Agent轨迹保存问题"""
import sys
import os
import logging
from pathlib import Path

# 配置日志显示所有级别
logging.basicConfig(level=logging.DEBUG)

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

# 首先测试导入
print("=== 测试导入 ===")
try:
    from backend.v1.app.agent.trace.trace_storage import trace_storage
    print("✅ trace_storage 导入成功")
    HAS_TRACE_STORAGE = True
except ImportError as e:
    print(f"❌ trace_storage 导入失败: {e}")
    HAS_TRACE_STORAGE = False

print(f"HAS_TRACE_STORAGE = {HAS_TRACE_STORAGE}")

# 测试数据库连接和表是否存在
print("\n=== 测试数据库连接 ===")
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.store.database.async_database import SessionLocal
from backend.v1.app.models.agent_trace import AgentTrace

async def test_db():
    try:
        async with SessionLocal() as db:
            # 尝试查询agent_traces表
            result = await db.execute("SELECT 1 FROM agent_traces LIMIT 1")
            print("✅ agent_traces表存在")
            return True
    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        if "doesn't exist" in str(e) or "不存在" in str(e):
            print("   原因: agent_traces表不存在")
        return False

table_exists = asyncio.run(test_db())

if not table_exists:
    print("\n=== 尝试创建agent_traces表 ===")
    from backend.store.database.async_database import engine
    from backend.v1.app.models.agent_trace import Base

    async def create_table():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, tables=[AgentTrace.__table__])
            print("✅ agent_traces表创建成功")
            return True
        except Exception as e:
            print(f"❌ 创建表失败: {e}")
            return False

    table_created = asyncio.run(create_table())
    if not table_created:
        print("无法创建表，退出测试")
        sys.exit(1)

# 测试保存轨迹
print("\n=== 测试保存轨迹 ===")
async def test_save_trace():
    try:
        await trace_storage.save_trace(
            session_id="test_session_001",
            user_input="测试问题",
            system_prompt="你是一个测试助手",
            model="test_model",
            temperature=0.7,
            max_tokens=2048,
            top_p=0.95,
            messages_history=[{"role": "user", "content": "测试问题"}],
            iterations=1,
            tool_calls=[],
            tool_results=[],
            final_answer="测试回答",
            cost_time=0.5,
            success=True,
            error_msg=None,
            user_id=1,
            project_id=1,
            meta_data={"test": "value"}
        )
        print("✅ 轨迹保存成功")

        # 查询验证
        async with SessionLocal() as db:
            result = await db.execute(
                AgentTrace.__table__.select()
                .order_by(AgentTrace.created_at.desc())
                .limit(1)
            )
            trace = result.scalar_one_or_none()
            if trace:
                print(f"   验证成功，轨迹ID: {trace.id}")
                return True
            else:
                print("❌ 保存后查询不到轨迹")
                return False
    except Exception as e:
        print(f"❌ 保存轨迹失败: {e}")
        import traceback
        traceback.print_exc()
        return False

save_success = asyncio.run(test_save_trace())

if save_success:
    print("\n🎉 所有测试通过！轨迹保存功能正常。")
else:
    print("\n❌ 测试失败。")
