# ScriptAgent工具调用测试说明

## 概述
本测试用于验证ScriptAgent在开放所有创作模式后，是否能够：
1. 自主选择最合适的创作模式
2. 根据需求主动调用相关工具
3. 工具调用成功并正确使用返回结果
4. 工具调用失败时能够自动回退到自主创作模式

## 前置条件
### 1. 环境配置
在项目根目录的`.env`文件中配置以下环境变量：
```env
# 豆包大模型配置
DOUBAO_SEED=doubao-seed
DOUBAO_API_KEY=your_api_key_here
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3

# 数据库配置（如果需要连接数据库查询模板/策略等）
DATABASE_URL=mysql+asyncmy://user:password@host:port/dbname
```

### 2. 依赖安装
确保已经安装了所有必要的依赖：
```bash
pip install -r requirements.txt
```

## 测试文件说明
| 文件名 | 说明 |
|--------|------|
| `test_script_agent_tool_calling.py` | 主测试文件，包含5个测试用例 |
| `run_tool_call_test.py` | 测试运行脚本，简化测试执行 |
| `test_outputs/` | 测试结果输出目录，每次测试会生成详细的JSON结果文件 |

## 测试用例说明

### 1. `test_auto_mode_basic_generation`
**测试目标**：验证auto模式下Agent能够自主选择合适的创作模式
**测试场景**：普通数码产品（蓝牙耳机），没有指定具体模式
**预期结果**：
- Agent成功生成符合格式的剧本
- 根据商品特点自主选择创作模式（可能自主创作，也可能调用爆款融合工具）
- 剧本包含3-5个场景，总时长符合要求

### 2. `test_auto_mode_hot_video_fusion`
**测试目标**：验证对于有明确分类的商品，Agent会自动调用爆款视频融合工具
**测试场景**：美妆类产品（美白精华液），属于爆款视频较多的品类
**预期结果**：
- Agent成功生成剧本
- 大概率会调用`hot_video_fusion_creation`工具查询同类爆款视频
- 生成的剧本会参考爆款视频的结构和创意

### 3. `test_similar_video_reference_mode`
**测试目标**：验证提供视频解析报告时，Agent会调用相似视频检索工具
**测试场景**：提供了一份美白精华液的爆款视频解析报告
**预期结果**：
- Agent成功生成剧本
- 会调用`search_similar_hot_videos`工具检索相似爆款案例
- 生成的剧本会参考相似视频的成功经验

### 4. `test_strategy_factor_mode`
**测试目标**：验证指定策略因子模式时，Agent会调用对应的工具
**测试场景**：明确指定使用策略因子模式生成家用破壁机剧本
**预期结果**：
- Agent成功生成剧本
- 会调用`strategy_factor_creation`工具获取创作策略
- 生成的剧本会遵循推荐的创作策略

### 5. `test_tool_call_fallback`
**测试目标**：验证工具调用失败时，Agent会自动回退到自主创作模式
**测试场景**：临时禁用所有工具，强制工具调用失败
**预期结果**：
- Agent不会因为工具调用失败而报错
- 自动切换到自主创作模式，成功生成剧本
- 生成的剧本仍然符合格式要求

## 运行测试

### 方式1：运行所有测试
```bash
cd backend/v1/app/agent/tests
python run_tool_call_test.py
```

### 方式2：运行指定测试
```bash
# 运行单个测试
python run_tool_call_test.py test_auto_mode_basic_generation

# 运行单个测试并显示详细输出
python run_tool_call_test.py test_auto_mode_hot_video_fusion -v
```

### 方式3：使用unittest命令运行
```bash
# 运行所有测试
python -m unittest test_script_agent_tool_calling.py -v

# 运行指定测试
python -m unittest test_script_agent_tool_calling.TestScriptAgentToolCalling.test_similar_video_reference_mode
```

## 测试结果说明
### 成功标识
- ✅ 剧本生成成功：表示Agent正常返回了符合格式的剧本
- 🔧 检测到工具调用：表示Agent确实调用了对应的工具
- ✅ 检测到XX工具调用：表示预期的工具被正确调用
- ℹ️  本次未调用工具：表示Agent选择了自主创作模式（属于正常情况）

### 输出文件
每次测试会在`test_outputs/`目录下生成一个JSON文件，包含：
- 最终生成的剧本内容
- 完整的迭代历史（每一步的思考和工具调用记录）
- 可用工具列表

### 典型成功输出示例
```
================================================================================
测试1: auto模式下普通商品剧本生成
================================================================================
✅ ScriptAgent初始化成功
✅ 可用工具: ['text_to_sql_inspiration', 'hot_video_fusion_creation', 'template_creation', 'strategy_factor_creation', 'search_similar_hot_videos']
✅ 剧本生成成功，共 4 个场景
🎬 剧本标题: 无线蓝牙耳机
📝 开场 hook: 还在为耳机续航短发愁吗？
🔧 检测到工具调用: 1 次
  1. 工具: hot_video_fusion_creation, 参数: {'category': '数码产品 > 音频设备 > 蓝牙耳机'}
📝 测试结果已保存到: test_outputs/test_auto_mode_basic_abc123.json
.
----------------------------------------------------------------------
Ran 1 test in 8.234s

OK
```

## 常见问题

### Q: 测试提示缺少环境变量
A: 请检查项目根目录的`.env`文件是否配置了正确的大模型API密钥和其他必要配置。

### Q: 测试运行失败，提示"模型调用失败"
A: 请检查：
1. API密钥是否正确
2. 网络是否能正常访问大模型API地址
3. 账户是否有足够的余额

### Q: Agent没有调用预期的工具怎么办？
A: 这是正常现象，因为Agent会根据实际情况自主判断是否需要调用工具。如果多次测试都没有调用任何工具，可以：
1. 检查系统提示词是否正确配置了工具调用的权限
2. 在测试用例的prompt中更明确地要求参考爆款视频或使用工具
3. 查看`test_outputs/`下的详细结果，分析Agent的思考过程

### Q: 工具调用返回空结果怎么办？
A: 可能是数据库中没有对应分类的爆款视频或模板数据，属于正常情况。Agent会自动回退到自主创作模式，不影响最终剧本生成。
