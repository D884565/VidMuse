<template>
  <div class="trace-timeline">
    <el-timeline>
      <!-- 用户输入 -->
      <el-timeline-item timestamp="用户输入" placement="top">
        <template #icon>
          <el-icon class="icon-user"><user /></el-icon>
        </template>
        <el-card class="timeline-card">
          <div class="card-header flex-between">
            <span class="title">用户问题</span>
            <el-button
              size="small"
              type="text"
              @click="copyToClipboard(trace.user_input)"
            >
              <el-icon><copy-document /></el-icon>
              复制
            </el-button>
          </div>
          <div class="card-content user-content">
            {{ trace.user_input }}
          </div>
        </el-card>
      </el-timeline-item>

      <!-- 系统提示 -->
      <el-timeline-item timestamp="系统提示" placement="top">
        <template #icon>
          <el-icon class="icon-system"><setting /></el-icon>
        </template>
        <el-card class="timeline-card">
          <div class="card-header flex-between">
            <span class="title">系统Prompt</span>
            <div class="actions">
              <el-button
                size="small"
                type="text"
                @click="showSystemPrompt = !showSystemPrompt"
              >
                {{ showSystemPrompt ? '收起' : '展开' }}
              </el-button>
              <el-button
                size="small"
                type="text"
                @click="copyToClipboard(trace.system_prompt)"
              >
                <el-icon><copy-document /></el-icon>
                复制
              </el-button>
            </div>
          </div>
          <div
            class="card-content system-content"
            :class="{ 'collapsed': !showSystemPrompt }"
            v-show="showSystemPrompt"
          >
            {{ trace.system_prompt }}
          </div>
        </el-card>
      </el-timeline-item>

      <!-- 推理过程 -->
      <template v-for="(item, index) in reasoningSteps" :key="index">
        <el-timeline-item :timestamp="item.title" placement="top">
          <template #icon>
            <el-icon :class="item.iconClass"><component :is="item.icon" /></el-icon>
          </template>
          <el-card class="timeline-card">
            <div class="card-header flex-between">
              <span class="title">{{ item.title }}</span>
              <el-button
                size="small"
                type="text"
                @click="copyToClipboard(item.content)"
                v-if="item.copyable"
              >
                <el-icon><copy-document /></el-icon>
                复制
              </el-button>
            </div>
            <div class="card-content" :class="item.contentClass">
              <pre v-if="item.isJson">{{ JSON.stringify(item.content, null, 2) }}</pre>
              <div v-else>{{ item.content }}</div>
            </div>
          </el-card>
        </el-timeline-item>
      </template>

      <!-- 最终回答 -->
      <el-timeline-item timestamp="最终回答" placement="top">
        <template #icon>
          <el-icon class="icon-answer"><chat-dot-round /></el-icon>
        </template>
        <el-card class="timeline-card">
          <div class="card-header flex-between">
            <span class="title">AI回答</span>
            <el-button
              size="small"
              type="text"
              @click="copyToClipboard(trace.final_answer)"
            >
              <el-icon><copy-document /></el-icon>
              复制
            </el-button>
          </div>
          <div class="card-content answer-content">
            {{ trace.final_answer }}
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { User, Setting, Tools, CircleCheck, ChatDotRound, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  trace: {
    type: Object,
    required: true
  }
})

const showSystemPrompt = ref(false)

// 处理推理步骤
const reasoningSteps = computed(() => {
  const steps = []
  const trace = props.trace

  // 如果有工具调用，添加到步骤中
  if (trace.tool_calls && trace.tool_calls.length > 0) {
    trace.tool_calls.forEach((call, idx) => {
      steps.push({
        title: `工具调用 #${idx + 1}`,
        icon: Tools,
        iconClass: 'icon-tool',
        content: call,
        isJson: true,
        copyable: true,
        contentClass: 'tool-content'
      })

      // 如果有对应的工具结果
      if (trace.tool_results && trace.tool_results[idx]) {
        steps.push({
          title: `工具返回 #${idx + 1}`,
          icon: CircleCheck,
          iconClass: 'icon-tool-result',
          content: trace.tool_results[idx],
          copyable: true,
          contentClass: 'tool-result-content'
        })
      }
    })
  }

  // 如果有错误信息
  if (!trace.success && trace.error_msg) {
    steps.push({
      title: '错误信息',
      icon: Warning,
      iconClass: 'icon-error',
      content: trace.error_msg,
      copyable: true,
      contentClass: 'error-content'
    })
  }

  return steps
})

const copyToClipboard = async (text) => {
  try {
    if (typeof text === 'object') {
      text = JSON.stringify(text, null, 2)
    }
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.trace-timeline {
  padding: 20px 0;
}

:deep(.el-timeline-item__tail) {
  border-left: 2px solid #e4e7ed;
}

.icon-user {
  background-color: #409eff;
  color: #fff;
}

.icon-system {
  background-color: #909399;
  color: #fff;
}

.icon-tool {
  background-color: #e6a23c;
  color: #fff;
}

.icon-tool-result {
  background-color: #67c23a;
  color: #fff;
}

.icon-answer {
  background-color: #67c23a;
  color: #fff;
}

.icon-error {
  background-color: #f56c6c;
  color: #fff;
}

:deep(.el-timeline-item__icon) {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.timeline-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.card-header {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.card-header .title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.card-content {
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
}

.user-content {
  background: #ecf5ff;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #409eff;
}

.system-content {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #909399;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.system-content.collapsed {
  max-height: 0;
  overflow: hidden;
  padding: 0;
}

.tool-content {
  background: #fdf6ec;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #e6a23c;
  font-family: 'Consolas', monospace;
  overflow-x: auto;
}

.tool-result-content {
  background: #f0f9ff;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #67c23a;
  font-family: 'Consolas', monospace;
  white-space: pre-wrap;
  overflow-x: auto;
}

.answer-content {
  background: #f0f9ff;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #67c23a;
}

.error-content {
  background: #fef0f0;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid #f56c6c;
  color: #f56c6c;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>