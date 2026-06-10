from typing import Tuple

# 错误码格式说明（遵循阿里巴巴开发守则）：
# 错误码为7位字符串：
# 第1位：错误来源
#   0：成功
#   A：用户端错误 - 用户提交的数据有问题、操作不合法等
#   B：系统错误 - 服务端内部错误、逻辑异常等
#   C：第三方错误 - 调用第三方服务出现的错误
# 第2-3位：模块代码
#   00：通用模块
#   01：用户模块
#   02：内容模块
#   03：AI模块
#   04：存储模块
#   05：视频生成模块
# 第4-7位：具体错误编号，从0001开始递增


# ==================== 通用错误码 (模块 00) ====================
# 成功码
SUCCESS: Tuple[str, str] = ("0000000", "操作成功")

# 用户端错误 A 类
CLIENT_ERROR: Tuple[str, str] = ("A000001", "用户端错误")
PARAM_ERROR: Tuple[str, str] = ("A000002", "请求参数错误")
PARAM_IS_NULL: Tuple[str, str] = ("A000003", "参数不能为空")
PARAM_FORMAT_ERROR: Tuple[str, str] = ("A000004", "参数格式错误")
PARAM_VALUE_INVALID: Tuple[str, str] = ("A000005", "参数值不合法")
REQUEST_METHOD_NOT_SUPPORTED: Tuple[str, str] = ("A000006", "请求方法不支持")
UNAUTHORIZED: Tuple[str, str] = ("A000007", "未授权访问")
LOGIN_EXPIRED: Tuple[str, str] = ("A000008", "登录已过期")
FORBIDDEN: Tuple[str, str] = ("A000009", "禁止访问")
RESOURCE_NOT_FOUND: Tuple[str, str] = ("A000010", "资源不存在")
RESOURCE_ALREADY_EXISTS: Tuple[str, str] = ("A000011", "资源已存在")
RESOURCE_CONFLICT: Tuple[str, str] = ("A000012", "资源冲突")
REQUEST_TOO_FREQUENT: Tuple[str, str] = ("A000013", "请求过于频繁")
OPERATION_TOO_FREQUENT: Tuple[str, str] = ("A000014", "操作过于频繁")
ILLEGAL_OPERATION: Tuple[str, str] = ("A000015", "非法操作")
BUSINESS_ERROR: Tuple[str, str] = ("A000016", "业务逻辑错误")

# 系统错误 B 类
SYSTEM_ERROR: Tuple[str, str] = ("B000001", "系统内部错误")
SYSTEM_BUSY: Tuple[str, str] = ("B000002", "系统繁忙，请稍后再试")
SYSTEM_TIMEOUT: Tuple[str, str] = ("B000003", "系统超时")
DATABASE_ERROR: Tuple[str, str] = ("B000004", "数据库访问错误")
DATABASE_TIMEOUT: Tuple[str, str] = ("B000005", "数据库访问超时")
CACHE_ERROR: Tuple[str, str] = ("B000006", "缓存访问错误")
FILE_OPERATION_ERROR: Tuple[str, str] = ("B000007", "文件操作错误")
IO_ERROR: Tuple[str, str] = ("B000008", "IO 错误")
CONFIG_ERROR: Tuple[str, str] = ("B000009", "配置错误")
RPC_ERROR: Tuple[str, str] = ("B000010", "远程调用错误")

# 第三方错误 C 类
THIRD_PARTY_ERROR: Tuple[str, str] = ("C000001", "第三方服务调用错误")
THIRD_PARTY_TIMEOUT: Tuple[str, str] = ("C000002", "第三方服务调用超时")
THIRD_PARTY_RESPONSE_ERROR: Tuple[str, str] = ("C000003", "第三方服务响应错误")
OSS_ERROR: Tuple[str, str] = ("C000004", "对象存储服务错误")
SMS_ERROR: Tuple[str, str] = ("C000005", "短信服务错误")
EMAIL_ERROR: Tuple[str, str] = ("C000006", "邮件服务错误")
AI_SERVICE_ERROR: Tuple[str, str] = ("C000007", "AI 服务调用错误")
PAYMENT_ERROR: Tuple[str, str] = ("C000008", "支付服务错误")


# ==================== 用户模块错误码 (模块 01) ====================
USER_ERROR: Tuple[str, str] = ("A010001", "用户模块错误")
USER_NOT_FOUND: Tuple[str, str] = ("A010002", "用户不存在")
USER_ALREADY_EXISTS: Tuple[str, str] = ("A010003", "用户已存在")
USERNAME_OR_PASSWORD_ERROR: Tuple[str, str] = ("A010004", "用户名或密码错误")
PASSWORD_ERROR: Tuple[str, str] = ("A010005", "密码错误")
ACCOUNT_DISABLED: Tuple[str, str] = ("A010006", "账号已被禁用")
ACCOUNT_LOCKED: Tuple[str, str] = ("A010007", "账号已被锁定")
ACCOUNT_EXPIRED: Tuple[str, str] = ("A010008", "账号已过期")
VERIFICATION_CODE_ERROR: Tuple[str, str] = ("A010009", "验证码错误")
VERIFICATION_CODE_EXPIRED: Tuple[str, str] = ("A010010", "验证码已过期")
EMAIL_ALREADY_EXISTS: Tuple[str, str] = ("A010011", "邮箱已被使用")
PHONE_ALREADY_EXISTS: Tuple[str, str] = ("A010012", "手机号已被使用")


# ==================== 内容模块错误码 (模块 02) ====================
CONTENT_ERROR: Tuple[str, str] = ("A020001", "内容模块错误")
CONTENT_NOT_FOUND: Tuple[str, str] = ("A020002", "内容不存在")
CONTENT_NOT_ALLOWED: Tuple[str, str] = ("A020003", "内容不合法")
CONTENT_AUDIT_FAILED: Tuple[str, str] = ("A020004", "内容审核未通过")
CONTENT_TOO_LONG: Tuple[str, str] = ("A020005", "内容过长")
CONTENT_EMPTY: Tuple[str, str] = ("A020006", "内容不能为空")


# ==================== AI 模块错误码 (模块 03) ====================
AI_ERROR: Tuple[str, str] = ("A030001", "AI 模块错误")
AI_GENERATE_FAILED: Tuple[str, str] = ("A030002", "AI 生成失败")
AI_PROMPT_TOO_LONG: Tuple[str, str] = ("A030003", "提示词过长")
AI_CONTENT_VIOLATION: Tuple[str, str] = ("A030004", "生成内容违规")
AI_QUOTA_EXHAUSTED: Tuple[str, str] = ("A030005", "AI 配额已用完")


# ==================== 存储模块错误码 (模块 04) ====================
STORAGE_ERROR: Tuple[str, str] = ("A040001", "存储模块错误")
FILE_NOT_FOUND: Tuple[str, str] = ("A040002", "文件不存在")
FILE_TOO_LARGE: Tuple[str, str] = ("A040003", "文件过大")
FILE_FORMAT_NOT_SUPPORTED: Tuple[str, str] = ("A040004", "文件格式不支持")
UPLOAD_FAILED: Tuple[str, str] = ("A040005", "文件上传失败")
DOWNLOAD_FAILED: Tuple[str, str] = ("A040006", "文件下载失败")
FILE_DELETE_FAILED: Tuple[str, str] = ("A040007", "文件删除失败")


# ==================== 视频生成模块错误码 (模块 05) ====================
VIDEO_ERROR: Tuple[str, str] = ("A050001", "视频生成模块错误")
VIDEO_GENERATE_FAILED: Tuple[str, str] = ("A050002", "视频生成失败")
VIDEO_RENDER_FAILED: Tuple[str, str] = ("A050003", "视频渲染失败")
VIDEO_TOO_LONG: Tuple[str, str] = ("A050004", "视频时长过长")
TEMPLATE_NOT_FOUND: Tuple[str, str] = ("A050005", "模板不存在")
MATERIAL_NOT_FOUND: Tuple[str, str] = ("A050006", "素材不存在")
GENERATE_QUOTA_EXHAUSTED: Tuple[str, str] = ("A050007", "生成配额已用完")


# ==================== 商品模块错误码 (模块 06) ====================
PRODUCT_ERROR: Tuple[str, str] = ("A060001", "商品模块错误")
PRODUCT_NOT_FOUND: Tuple[str, str] = ("A060002", "商品不存在")
PRODUCT_NO_PERMISSION: Tuple[str, str] = ("A060003", "无权限操作此商品")
PRODUCT_URL_INVALID: Tuple[str, str] = ("A060004", "商品链接格式错误")
PRODUCT_CRAWL_FAILED: Tuple[str, str] = ("A060005", "商品抓取失败")
