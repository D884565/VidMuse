<template>
  <div class="trace-detail">
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
          <el-tag @click="goToSessionTrace(trace.session_id)" type="info" effect="plain" style="cursor: pointer">
            {{ trace.session_id }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="用户ID">{{ trace.user_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目ID">{{ trace.project_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ trace.model }}</el-descriptions-item>
        <el-descriptions-item label="温度">{{ trace.temperature }}</el-descriptions-item>
        <el-descriptions-item label="最大Token">{{ trace.max_tokens }}</el-descriptions-item>
        <el-descriptions-item label="Top P">{{ trace.top_p }}</el-descriptions-item>
        <el-descriptions-item label="迭代次数">{{ trace.iterations }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ trace.cost_time?.toFixed(2) }}s</el-descriptions-item>
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
      <TraceTimeline :trace="trace" v-if="trace.id" />
      <el-empty description="暂无数据" v-else />
    </el-card>
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
    ElMessage.error('加载轨迹详情失败')
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
