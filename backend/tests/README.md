# 向量数据库测试说明

## 前置条件
1. 确保ChromaDB服务已启动并运行正常：
   ```bash
   chroma run --host localhost --port 8001
   ```
2. 确保配置文件`config.py`中的ChromaDB配置正确：
   ```python
   VECTOR_DB_TYPE = "chromadb"
   CHROMADB_HOST = "localhost"
   CHROMADB_PORT = 8001
   ```
3. 安装必要依赖：
   ```bash
   pip install pytest chromadb
   ```

## 运行测试

### 方式1：直接运行测试文件
```bash
cd backend
python -m tests.test_vector_collection
```

### 方式2：使用pytest运行
```bash
cd backend
pytest tests/test_vector_collection.py -v
```

## 测试内容
测试会自动完成以下验证：
✅ 向量数据库连接是否正常
✅ 产品知识库DAO的增、查、删功能
✅ 片段知识库DAO的增、查、删功能  
✅ 视频知识库DAO的增、查、删功能
✅ 多集合同时操作（数据隔离）
✅ 底层直接操作集合功能

## 注意事项
1. 测试会自动创建带`test_`前缀的集合，不会影响正式数据
2. 测试完成后会自动清理所有测试用集合
3. 如果测试失败，会自动打印错误信息并清理数据
4. 支持ChromaDB和Milvus自动切换，配置变更后无需修改测试代码

## 常见问题
### 1. 连接ChromaDB失败
- 检查ChromaDB服务是否启动
- 检查host和port配置是否正确
- 检查防火墙是否允许访问8001端口

### 2. 测试数据未清理
- 可手动删除ChromaDB中所有带`test_`前缀的集合
- 或重新运行测试，会自动清理之前的测试数据
