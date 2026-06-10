# 分布式ID生成器

基于Redis和雪花算法实现的分布式唯一ID生成器，支持高并发、分布式环境下的ID生成。

## 功能特性

1. **雪花算法实现**：ID包含时间戳、数据中心ID、工作节点ID、序列号，保证有序性和唯一性
2. **Redis自动分配Worker ID**：无需手动配置每个节点的Worker ID，通过Redis自动分配和管理
3. **自动续期机制**：Worker ID定期续期，避免进程异常退出导致的ID浪费
4. **时钟回退处理**：内置时钟回退检测和处理机制，保证ID不重复
5. **全局单例支持**：提供全局初始化和访问接口，方便使用

## ID结构

```
+--------------------------------------------------------------------------+
| 1位 符号位 | 41位 时间戳(毫秒) | 5位 数据中心ID | 5位 工作节点ID | 12位 序列号 |
+--------------------------------------------------------------------------+
```

- 符号位：始终为0，表示正数
- 时间戳：从2024-01-01开始计算，可以使用69年
- 数据中心ID：支持最多32个数据中心
- 工作节点ID：支持最多32个工作节点（每个数据中心）
- 序列号：同一毫秒内最多生成4096个ID

## 使用方法

### 1. 全局初始化（推荐）

在应用启动时初始化全局生成器：

```python
from backend.framework import initialize_global_generator

# 在应用启动时调用
async def startup():
    await initialize_global_generator(service_name="your_service_name", data_center_id=0)
```

在需要生成ID的地方直接使用：

```python
from backend.framework import get_next_id, get_next_string_id

# 生成整数ID
id = await get_next_id()

# 生成字符串ID
id_str = await get_next_string_id()
```

在应用关闭时释放资源：

```python
from backend.framework import close_global_generator

async def shutdown():
    await close_global_generator()
```

### 2. 单独使用实例

如果需要多个生成器实例，可以单独创建：

```python
from backend.framework import SnowflakeIdGenerator

# 创建生成器
generator = await SnowflakeIdGenerator.create_with_redis_allocator(
    service_name="your_service_name",
    data_center_id=0
)

# 生成ID
id = await generator.generate_id()

# 关闭生成器
await generator.close()
```

### 3. 手动指定Worker ID

如果不使用Redis自动分配，可以手动指定Worker ID：

```python
from backend.framework import SnowflakeIdGenerator

generator = SnowflakeIdGenerator(worker_id=1, data_center_id=0)
id = await generator.generate_id()
```

## 解析ID

可以解析已生成的ID，获取各个组成部分：

```python
from backend.framework import SnowflakeIdGenerator

generator = SnowflakeIdGenerator(worker_id=1, data_center_id=0)
timestamp, data_center_id, worker_id, sequence = generator.parse_id(id)
```

## 配置说明

相关配置在`config.py`中：

- `REDIS_HOST`: Redis服务器地址
- `REDIS_PORT`: Redis服务器端口

## 注意事项

1. 确保Redis服务正常运行，否则无法自动分配Worker ID
2. 不同服务请使用不同的`service_name`，避免Worker ID冲突
3. 数据中心ID需要手动配置，不同数据中心使用不同的ID
4. 应用关闭时请调用`close_global_generator()`释放资源
