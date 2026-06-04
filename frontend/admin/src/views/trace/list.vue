<template>
  <div class="trace-list">
    <!-- 搜索表单 -->
    <SearchForm
      :fields="searchFields"
      :initial-form="searchForm"
      @search="handleSearch"
      @reset="handleReset"
    >
      <template #extra>
        <el-button type="success" @click="handleExport" :loading="exportLoading">
          <el-icon><download /></el-icon>
          导出数据
        </el-button>
      </template>
    </SearchForm>

    <!-- 表格 -->
    <CommonTable
      :columns="tableColumns"
      :table-data="tableData"
      :loading="loading"
      :pagination="pagination"
      @update:pagination="val => pagination = val"
      @query="loadData"
    >
      <!-- 用户输入列 -->
      <template #user_input="{ row }">
        <el-tooltip :content="row.user_input" placement="top">
          <span class="text-ellipsis">{{ row.user_input }}</span>
        </el-tooltip>
      </template>

      <!-- 状态列 -->
      <template #status="{ row }">
        <el-tag :type="row.success ? 'success' : 'danger'">
          {{ row.success ? '成功' : '失败' }}
        </el-tag>
      </template>

      <!-- 耗时列 -->
      <template #cost_time="{ row }">
        <span :class="{ 'text-red': row.cost_time > 10 }">
          {{ (row.cost_time || 0).toFixed(2) }}s
        </span>
      </template>

      <!-- 操作列 -->
      <template #action="{ row }">
        <el-button
          type="primary"
          size="small"
          @click="$router.push(`/trace/${row.id}`)"
        >
          查看详情
        </el-button>
      </template>
    </CommonTable>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getTraceList, exportTraces } from '@/api/modules/trace'
import SearchForm from '@/components/SearchForm/index.vue'
import CommonTable from '@/components/CommonTable/index.vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import saveAs from 'file-saver'

const loading = ref(false)
const exportLoading = ref(false)

// 搜索表单配置
const searchForm = reactive({
  session_id: '',
  user_id: '',
  model: '',
  success: '',
  time_range: '',
  keyword: ''
})

const searchFields = [
  {
    prop: 'session_id',
    label: '会话ID',
    type: 'input',
    placeholder: '请输入会话ID'
  },
  {
    prop: 'user_id',
    label: '用户ID',
    type: 'input',
    placeholder: '请输入用户ID'
  },
  {
    prop: 'model',
    label: '模型',
    type: 'input',
    placeholder: '请输入模型名称'
  },
  {
    prop: 'success',
    label: '执行状态',
    type: 'select',
    options: [
      { label: '全部', value: '' },
      { label: '成功', value: true },
      { label: '失败', value: false }
    ]
  },
  {
    prop: 'time_range',
    label: '时间范围',
    type: 'daterange'
  },
  {
    prop: 'keyword',
    label: '关键词',
    type: 'input',
    placeholder: '搜索用户输入/回答',
    width: '250px'
  }
]

// 表格列配置
const tableColumns = [
  {
    prop: 'id',
    label: 'ID',
    width: '80'
  },
  {
    prop: 'session_id',
    label: '会话ID',
    width: '120',
    formatter: (val) => val ? val.substring(0, 8) + '...' : '-'
  },
  {
    prop: 'user_input',
    label: '用户输入',
    slot: 'user_input',
    minWidth: '200'
  },
  {
    prop: 'model',
    label: '模型',
    width: '120'
  },
  {
    prop: 'iterations',
    label: '迭代次数',
    width: '100'
  },
  {
    prop: 'cost_time',
    label: '耗时',
    width: '100',
    slot: 'cost_time'
  },
  {
    prop: 'success',
    label: '状态',
    width: '100',
    slot: 'status'
  },
  {
    prop: 'created_at',
    label: '创建时间',
    width: '180',
    formatter: (val) => dayjs(val).format('YYYY-MM-DD HH:mm:ss')
  },
  {
    prop: 'action',
    label: '操作',
    width: '120',
    slot: 'action',
    fixed: 'right'
  }
]

// 分页配置
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const tableData = ref([])

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
      session_id: searchForm.session_id || undefined,
      user_id: searchForm.user_id ? Number(searchForm.user_id) : undefined,
      model: searchForm.model || undefined,
      success: searchForm.success !== '' ? searchForm.success : undefined,
      keyword: searchForm.keyword || undefined,
      start_time: searchForm.time_range?.[0] || undefined,
      end_time: searchForm.time_range?.[1] || undefined
    }

    const res = await getTraceList(params)
    tableData.value = res.list || []
    pagination.total = res.total || 0
  } catch (error) {
    console.error('加载轨迹列表失败:', error)
    ElMessage.error('加载轨迹列表失败，使用模拟数据展示')
    // 模拟数据
    tableData.value = Array.from({ length: 10 }, (_, i) => ({
      id: 1200 + i,
      session_id: `sess_${Math.random().toString(36).substring(2, 10)}`,
      user_input: ['帮我写一个前端组件', '分析这个数据', '生成一份报告', '优化这段代码', '解释这个算法'][Math.floor(Math.random() * 5)],
      model: ['GPT-4o', 'Claude 3 Opus', 'Claude 3 Sonnet', 'GPT-3.5 Turbo'][Math.floor(Math.random() * 4)],
      iterations: Math.floor(Math.random() * 10) + 1,
      cost_time: Math.random() * 15 + 0.5,
      success: Math.random() > 0.1,
      created_at: dayjs().subtract(i * 30, 'minute').format('YYYY-MM-DD HH:mm:ss')
    }))
    pagination.total = 100
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = (params) => {
  Object.assign(searchForm, params)
  pagination.page = 1
  loadData()
}

// 重置
const handleReset = (params) => {
  Object.assign(searchForm, params)
  pagination.page = 1
  loadData()
}

// 导出数据
const handleExport = async () => {
  exportLoading.value = true
  try {
    const params = {
      session_id: searchForm.session_id || undefined,
      user_id: searchForm.user_id ? Number(searchForm.user_id) : undefined,
      success: searchForm.success !== '' ? searchForm.success : undefined,
      start_time: searchForm.time_range?.[0] || undefined,
      end_time: searchForm.time_range?.[1] || undefined
    }

    const blob = await exportTraces(params)
    const filename = `trace_export_${dayjs().format('YYYYMMDDHHmmss')}.xlsx`
    saveAs(blob, filename)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.text-ellipsis {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-red {
  color: #f56c6c;
  font-weight: 500;
}
</style>