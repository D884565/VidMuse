"""
流水线上下文键名常量定义
统一管理所有上下文键名，避免硬编码和拼写错误
"""

# 通用ID类键
VIDEO_ID = "video_id"
PRODUCT_ID = "product_id"
SOURCE_ID = "source_id"
OBJECT_NAME = "object_name"
IMAGE_SET_ID = "image_set_id"
SLICE_ID = "slice_id"

# 视频拆分处理器输出
SLICE_COUNT = "count"
SLICES_URL = "slices_url"
IMAGES_URL = "images_url"
SLICES_OBJECT_NAME = "slices_object_name"
IMAGES_OBJECT_NAME = "images_object_name"
SLICE_COVER_URLS = "slice_cover_urls"

# 视频理解处理器输出
UNDERSTOOD_SLICES = "understood_slices"
EMBED_SLICES = "embed_slices"

# 切片生成处理器输出
SLICE_FILES = "slice_files"
SLICE_DATA = "slice_data"

# 分片校验相关键
VALID_SLICES = "valid_slices"
INVALID_SLICES = "invalid_slices"
SLICE_VALIDATION_SUMMARY = "slice_validation_summary"

# 视频聚合处理器输出
AGGREGATED_VIDEO_DATA = "aggregated_video_data"
SEGMENT_LIST = "segment_list"
ALL_SCRIPT_LINES = "all_script_lines"
VIDEO_FILE = "video_file"
VIDEO_DATA = "video_data"

# 视频整体理解处理器输出
AI_FEATURES = "ai_features"
EMBED_VIDEO = "embed_video"

# 视频整体校验相关键
VALID_VIDEO = "valid_video"
INVALID_VIDEO = "invalid_video"
VIDEO_VALIDATION_SUMMARY = "video_validation_summary"

# 商品理解处理器输出
PRODUCT_UNDERSTANDING = "product_understanding"
IMAGES = "images"
DESCRIPTION = "description"
PRODUCT_DATA = "product_data"

# 商品校验相关键
VALID_PRODUCT = "valid_product"
INVALID_PRODUCT = "invalid_product"
PRODUCT_VALIDATION_SUMMARY = "product_validation_summary"

# 向量化处理器输出
VECTORIZATION_RESULT = "vectorization_result"
META_DATA = "meta_data"
