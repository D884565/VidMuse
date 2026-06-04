<template>
  <div class="trace-detail" v-loading="loading">
    <template v-if="trace.id">
      <!-- 顶部操作栏 -->
      <div class="page-header mb-20 flex-between">
        <div class="header-left">
          <el-button @click="$router.back()">
            <el-icon><arrow-left /></el-icon>
            返回列表
          </el-button>
          <span class="page-title">轨迹详情 #{{ trace.id }}</span>
        </div>
        <div class="header-right">
          <JsonViewer :data="trace" />
        </div>
      </div>

      <!-- 基础信息卡片 -->
      <el-card title="基础信息" class="mb-20">
        <el-descriptions :column="4" border>
          <el-descriptions-item label="轨迹ID">{{ trace.id }}</el-descriptions-item>
          <el-descriptions-item label="会话ID">
            <el-tag @click="goToSessionTrace(trace.session_id)" type="info" effect="plain" style="cursor: pointer" v-if="trace.session_id">
              {{ trace.session_id }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="用户ID">{{ trace.user_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目ID">{{ trace.project_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ trace.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="温度">{{ trace.temperature ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="最大Token">{{ trace.max_tokens ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="Top P">{{ trace.top_p ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="迭代次数">{{ trace.iterations ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ (trace.cost_time || 0).toFixed(2) }}s</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="trace.success ? 'success' : 'danger'">
              {{ trace.success ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ trace.created_at ? dayjs(trace.created_at).format('YYYY-MM-DD HH:mm:ss') : '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 推理链路时间线 -->
      <el-card title="推理链路" class="mb-20">
        <TraceTimeline :trace="trace" v-if="trace.steps?.length" />
        <el-empty description="暂无推理链路数据" v-else />
      </el-card>
    </template>
    <el-empty description="轨迹数据不存在" v-else-if="!loading" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTraceDetail } from '@/api/modules/trace'
import TraceTimeline from '@/components/TraceTimeline/index.vue'
import JsonViewer from '@/components/JsonViewer/index.vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const traceId = route.params.id
const trace = ref({})
const loading = ref(false)

const loadTraceDetail = async () => {
  loading.value = true
  try {
    const res = await getTraceDetail(traceId)
    trace.value = res
  } catch (error) {
    console.error('加载轨迹详情失败:', error)
    ElMessage.error('加载轨迹详情失败，使用模拟数据展示')
    // 模拟数据
    trace.value = {
      id: traceId,
      session_id: `sess_${Math.random().toString(36).substring(2, 10)}`,
      user_id: 12345,
      project_id: 'proj_abc123',
      model: 'Claude 3 Opus',
      temperature: 0.7,
      max_tokens: 4096,
      top_p: 0.9,
      iterations: 3,
      cost_time: 4.56,
      success: true,
      created_at: dayjs().subtract(2, 'hour').toISOString(),
      user_input: '帮我写一个Vue3的组件，实现一个可拖拽的表格',
      output: '好的，这是一个可拖拽表格的实现...',
      steps: [
        {
          type: 'user_input',
          content: '帮我写一个Vue3的组件，实现一个可拖拽的表格',
          timestamp: dayjs().subtract(2, 'hour').toISOString()
        },
        {
          type: 'tool_call',
          name: 'web_search',
          content: '搜索Vue3拖拽表格实现方案',
          timestamp: dayjs().subtract(2, 'hour').add(30, 'second').toISOString()
        },
        {
          type: 'tool_result',
          name: 'web_search',
          content: '找到了多个实现方案，包括SortableJS和vue-slicksort等库',
          timestamp: dayjs().subtract(2, 'hour').add(45, 'second').toISOString()
        },
        {
          type: 'thinking',
          content: '选择SortableJS作为基础库，因为它功能强大且支持Vue3',
          timestamp: dayjs().subtract(2, 'hour').add(50, 'second').toISOString()
        },
        {
          type: 'output',
          content: '好的，这是一个可拖拽表格的实现...',
          timestamp: dayjs().subtract(2, 'hour').add(4.56, 'minute').toISOString()
        }
      ]
    }
  } finally {
    loading.value = false
  }
}

const goToSessionTrace = (sessionId) => {
  router.push({
    path: '/trace',
    query: { session_id: sessionId }
  })
}

onMounted(() => {
  if (traceId) {
    loadTraceDetail()
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
}

.page-header .page-title {
  font-size: 20px;
  font-weight: 600;
  margin-left: 20px;
  color: #303133;
}
</style>
