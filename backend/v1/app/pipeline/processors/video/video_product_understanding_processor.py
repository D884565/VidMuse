from typing import Dict, Any
import json
import logging
import asyncio
import inspect

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.pipeline.utils import prompt_manager
from backend.providers import VolcanoLLM, VideoUnderstandingRequest

logger = logging.getLogger(__name__)


class VideoProductUnderstandingProcessor(BaseProcessor):
    """
    视频商品理解处理器
    直接将视频发送给大模型进行商品理解，输出product.json作为ai_features
    输出格式与图片/文本理解保持一致，方便后续统一处理
    """

    def __init__(self, llm_client=None):
        """
        初始化视频商品理解处理器
        """
        # 初始化大模型客户端和商品理解提示词
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        self.product_prompt = prompt_manager.get_product_understanding_prompt()

    def _run_async(self, coro):
        """
        从同步上下文中运行异步函数，处理已有事件循环的情况
        :param coro: 要运行的协程
        :return: 协程的返回值
        """
        try:
            # 检查是否有正在运行的事件循环
            loop = asyncio.get_running_loop()
            # 如果有运行中的循环，在新线程中运行异步函数避免死锁
            import threading
            result = None
            def run_in_thread():
                nonlocal result
                # 新线程中创建新的事件循环
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            return result
        except RuntimeError:
            # 没有运行中的循环，直接使用asyncio.run
            return asyncio.run(coro)

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频商品理解逻辑
        直接将视频发送给大模型，获取商品理解结果

        输入（从上下文获取）：
        - video_id: str 视频ID
        - video_url: str 视频URL（必须）
        - video_duration: int 视频时长（毫秒，可选）
        - asset_id: str 关联的资产ID（可选）

        输出（写入上下文）：
        - product_understanding: Dict 商品理解结果，与图片/文本理解格式一致
        - ai_features: Dict 包含product.json的AI特征结果

        :param context: 流水线上下文
        :return: 修改后的上下文
        """
        video_id = context.get("video_id") or context.get("product_id") or context.get("asset_id")
        video_url = context.get("video_url")
        video_duration = context.get("video_duration", 0)

        if not video_url:
            raise ValueError("video_url is required for video product understanding")
        if not video_id:
            raise ValueError("video_id, product_id or asset_id is required")

        try:
            logger.info(f"开始处理商品视频，video_id: {video_id}, video_url: {video_url}")

            # 构建视频理解请求
            request = VideoUnderstandingRequest(
                video_url=video_url,
                prompt=self.product_prompt,
                max_tokens=2048,
                temperature=0.7,
                top_p=0.9
            )

            # 调用大模型接口
            if inspect.iscoroutinefunction(self.llm_client.video_understanding):
                coro = self.llm_client.video_understanding(request)
                response = self._run_async(coro)
            elif inspect.iscoroutinefunction(self.llm_client.video_understanding_response):
                coro = self.llm_client.video_understanding_response(request)
                response = self._run_async(coro)
            else:
                # 尝试调用同步方法
                if hasattr(self.llm_client, 'video_understanding'):
                    response = self.llm_client.video_understanding(request)
                elif hasattr(self.llm_client, 'video_understanding_response'):
                    response = self.llm_client.video_understanding_response(request)
                else:
                    raise ValueError("LLM client does not support video understanding")

            # 解析返回结果，与图片/文本理解保持相同的解析逻辑
            def clean_and_parse_json(content: str) -> Dict[str, Any]:
                """
                增强版JSON解析器，处理各种格式问题
                :param content: 待解析的内容
                :return: 解析后的字典
                """
                import re
                import ast

                # 第一步：移除markdown代码块标记
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                # 第二步：提取最外层的JSON对象
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    content = content[start_idx:end_idx + 1]

                # 第三步：预处理：移除经常出问题的$schema字段，避免解析失败
                # 这个字段对业务逻辑不重要，且经常被大模型输出错误
                content = re.sub(r'"\$schema":\s*[^,]+,?', '', content)
                # 移除可能的空行和多余逗号
                content = re.sub(r',\s*,', ',', content)
                content = re.sub(r'{\s*,', '{', content)

                # 第四步：基础清理
                # 移除各种注释
                content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

                # 优先尝试demjson3解析，它的容错能力最强
                try:
                    import demjson3
                    return demjson3.decode(content, strict=False)
                except Exception as e:
                    logger.warning(f"demjson3解析失败，尝试标准JSON解析: {str(e)}")

                # 第四步：深度格式修复
                # 处理未闭合的引号
                def fix_unclosed_quotes(s: str) -> str:
                    """修复未闭合的双引号"""
                    quotes = []
                    escaped = False
                    for i, c in enumerate(s):
                        if c == '\\' and not escaped:
                            escaped = True
                            continue
                        if c == '"' and not escaped:
                            quotes.append(i)
                        escaped = False

                    # 如果引号数量是奇数，在末尾补一个
                    if len(quotes) % 2 != 0:
                        s += '"'
                    return s

                content = fix_unclosed_quotes(content)

                # 处理多余的逗号
                content = re.sub(r',\s*([}\]])', r'\1', content)

                # 尝试标准JSON解析
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"标准JSON解析失败: {str(e)}")

                # 尝试使用ast.literal_eval解析（可以处理更多Python风格的语法）
                try:
                    # 先替换true/false/null为Python风格的True/False/None
                    py_content = content.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                    return ast.literal_eval(py_content)
                except Exception as e:
                    logger.warning(f"ast.literal_eval解析失败: {str(e)}")

                # 尝试逐行修复缺失的逗号
                try:
                    lines = content.split('\n')
                    fixed_lines = []
                    in_string = False
                    escaped = False

                    for i, line in enumerate(lines):
                        line = line.rstrip()
                        if not line:
                            continue

                        # 检查当前行是否在字符串中
                        for c in line:
                            if c == '\\' and not escaped:
                                escaped = True
                                continue
                            if c == '"' and not escaped:
                                in_string = not in_string
                            escaped = False

                        # 如果不在字符串中，且行不是以逗号、{、[结尾，并且下一行不是以}、]开头，添加逗号
                        if (not in_string
                            and i < len(lines) - 1
                            and not line.endswith((',', '{', '['))
                            and not lines[i+1].strip().startswith(('}', ']'))):
                            line += ','

                        fixed_lines.append(line)

                    content = '\n'.join(fixed_lines)

                    # 再次尝试解析
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        pass

                    try:
                        import demjson3
                        return demjson3.decode(content, strict=False)
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"逐行修复失败: {str(e)}")

                # 尝试手动修复常见的截断问题
                logger.warning("尝试手动修复截断问题...")
                try:
                    # 修复不完整的$schema字段
                    content = re.sub(r'"\$schema":\s*"http:[^"]*$', r'"$schema": "http://json-schema.org/draft-07/schema#",', content, flags=re.MULTILINE)

                    # 尝试补全缺失的引号
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        # 查找类似 "key": "value 这样缺少闭合引号的行
                        match = re.match(r'(\s*"[^"]+":\s*")([^"]*)$', line)
                        if match:
                            lines[i] = match.group(1) + match.group(2) + '",'

                    content = '\n'.join(lines)

                    # 再次尝试解析
                    import demjson3
                    return demjson3.decode(content, strict=False)
                except Exception as e:
                    logger.error(f"手动修复也失败: {str(e)}")

                # 所有解析尝试都失败
                logger.error(f"所有JSON解析尝试都失败")
                logger.error(f"原始内容预览: {content[:2000]}...")
                raise ValueError(f"JSON解析失败: {str(e)}")

            try:
                understanding_result = clean_and_parse_json(response.content)
            except Exception as e:
                logger.error(f"JSON解析最终失败: {str(e)}", exc_info=True)
                # 兜底返回结构
                understanding_result = {
                    "商品名称": "视频商品理解结果",
                    "商品分类": "未分类",
                    "核心卖点数组": [],
                    "适用场景数组": [],
                    "解析错误": str(e),
                    "原始内容预览": response.content[:500] + "..." if len(response.content) > 500 else response.content
                }

            # 存储结果，格式与图片/文本理解完全一致
            context.set("product_understanding", understanding_result)

            # 将结果作为product.json存储到ai_features中
            ai_features = context.get("ai_features", {})
            ai_features["product.json"] = json.dumps(understanding_result, ensure_ascii=False, indent=2)
            context.set("ai_features", ai_features)

            logger.info(f"视频商品理解完成，video_id: {video_id}")

        except Exception as e:
            logger.error(f"视频商品理解失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"视频商品理解失败: {str(e)}"))

        return context
