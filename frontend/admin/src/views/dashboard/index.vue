<template>
  <div class="dashboard">
    <!-- 指标卡片 -->
    <el-row :gutter="20" class="mb-20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <p class="stat-label">总调用次数</p>
              <h3 class="stat-value">{{ stats.total_count || 0 }}</h3>
              <p class="stat-change positive" v-if="stats.change_rate">
                <el-icon><arrow-up /></el-icon>
                {{ stats.change_rate }}%
              </p>
            </div>
            <div class="stat-icon blue">
              <el-icon><trend-charts /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <p class="stat-label">成功率</p>
              <h3 class="stat-value">{{ (stats.success_rate * 100 || 0).toFixed(2) }}%</h3>
              <el-progress
                :percentage="(stats.success_rate * 100 || 0).toFixed(0)"
                :show-text="false"
                :color="successRateColor"
                height="8px"
              />
            </div>
            <div class="stat-icon green">
              <el-icon><circle-check /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <p class="stat-label">平均耗时</p>
              <h3 class="stat-value">{{ (stats.avg_cost_time || 0).toFixed(2) }}s</h3>
              <p class="stat-desc">近{{ periodLabel }}平均值</p>
            </div>
            <div class="stat-icon orange">
              <el-icon><timer /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <p class="stat-label">工具调用次数</p>
              <h3 class="stat-value">{{ stats.total_tool_calls || 0 }}</h3>
              <p class="stat-desc">总调用次数</p>
            </div>
            <div class="stat-icon purple">
              <el-icon><tools /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计周期选择 -->
    <div class="period-selector mb-20">
      <span class="label">统计周期：</span>
      <el-radio-group v-model="period" @change="loadStats">
        <el-radio-button label="1d">最近1天</el-radio-button>
        <el-radio-button label="7d">最近7天</el-radio-button>
        <el-radio-button label="30d">最近30天</el-radio-button>
        <el-radio-button label="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 图表区域 -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card title="调用量趋势" class="chart-card">
          <v-chart
            :option="trendChartOption"
            :autoresize="true"
            style="height: 400px"
          />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card title="模型使用占比" class="chart-card mb-20">
          <v-chart
            :option="modelPieOption"
            :autoresize="true"
            style="height: 200px"
          />
        </el-card>
        <el-card title="耗时分布" class="chart-card">
          <v-chart
            :option="costBarOption"
            :autoresize="true"
            style="height: 180px"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近异常列表 -->
    <el-card title="最近异常记录" class="mt-20">
      <el-table :data="recentErrors" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_input" label="用户输入" show-overflow-tooltip />
        <el-table-column prop="model" label="模型" width="120" />
        <el-table-column prop="error_msg" label="错误信息" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="scope">
            <el-button
              type="primary"
              link
              @click="$router.push(`/trace/${scope.row.id}`)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getTraceStats, getTraceList } from '@/api/modules/trace'
import dayjs from 'dayjs'

const loading = ref(false)
const period = ref('7d')
const stats = ref({})
const recentErrors = ref([])

const periodLabel = computed(() => {
  const labels = {
    '1d': '1天',
    '7d': '7天',
    '30d': '30天',
    'all': '全部'
  }
  return labels[period.value] || '7天'
})

const successRateColor = computed(() => {
  const rate = stats.value.success_rate || 0
  if (rate >= 0.95) return '#67c23a'
  if (rate >= 0.8) return '#e6a23c'
  return '#f56c6c'
})

// 调用量趋势图配置
const trendChartOption = computed(() => {
  return {
    tooltip: {
      trigger: 'axis'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: Array.from({ length: 7 }, (_, i) => dayjs().subtract(6 - i, 'day').format('MM-DD'))
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '调用量',
        type: 'line',
        smooth: true,
        data: [120, 132, 101, 134, 90, 230, 210],
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
              { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
            ]
          }
        },
        lineStyle: {
          color: '#667eea'
        },
        itemStyle: {
          color: '#667eea'
        }
      }
    ]
  }
})

// 模型占比饼图配置
const modelPieOption = computed(() => {
  return {
    tooltip: {
      trigger: 'item'
    },
    legend: {
      orient: 'horizontal',
      bottom: '0'
    },
    series: [
      {
        name: '模型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: [
          { value: 1048, name: 'Claude 3 Opus' },
          { value: 735, name: 'GPT-4o' },
          { value: 580, name: 'Claude 3 Sonnet' },
          { value: 484, name: 'GPT-3.5 Turbo' }
        ]
      }
    ]
  }
})

// 耗时分布柱状图配置
const costBarOption = computed(() => {
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['0-1s', '1-3s', '3-5s', '5-10s', '>10s']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '数量',
        type: 'bar',
        data: [320, 756, 480, 234, 120],
        itemStyle: {
          color: '#f39c12'
        }
      }
    ]
  }
})

// 加载统计数据
const loadStats = async () => {
  loading.value = true
  try {
    const res = await getTraceStats({ period: period.value })
    stats.value = res
  } catch (error) {
    console.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败，使用模拟数据展示')
    // 模拟数据
    stats.value = {
      total_count: 1258,
      success_rate: 0.982,
      avg_cost_time: 2.34,
      total_tool_calls: 3421,
      change_rate: 12.5
    }
  } finally {
    loading.value = false
  }
}

// 加载最近异常
const loadRecentErrors = async () => {
  try {
    const res = await getTraceList({
      success: false,
      page_size: 10,
      page: 1
    })
    recentErrors.value = res.list || []
  } catch (error) {
    console.error('加载异常列表失败:', error)
    // 模拟数据
    recentErrors.value = [
      {
        id: 1234,
        user_input: '帮我写一个Python爬虫',
        model: 'GPT-4o',
        error_msg: '网络超时，请稍后重试',
        created_at: '2024-06-04 14:30:00'
      },
      {
        id: 1233,
        user_input: '分析这个PDF文件的内容',
        model: 'Claude 3 Opus',
        error_msg: '文件解析失败，格式不支持',
        created_at: '2024-06-04 13:15:00'
      },
      {
        id: 1232,
        user_input: '生成一份市场分析报告',
        model: 'Claude 3 Sonnet',
        error_msg: 'API调用限额已用完',
        created_at: '2024-06-04 11:45:00'
      }
    ]
  }
}

onMounted(() => {
  loadStats()
  loadRecentErrors()
})
</script>

<style scoped>
.stat-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.stat-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-info .stat-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
}

.stat-info .stat-value {
  color: #303133;
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 8px;
}

.stat-info .stat-change {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.stat-change.positive {
  color: #67c23a;
}

.stat-change.negative {
  color: #f56c6c;
}

.stat-info .stat-desc {
  color: #909399;
  font-size: 12px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
}

.stat-icon.blue {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-icon.green {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
}

.stat-icon.orange {
  background: linear-gradient(135deg, #f39c12 0%, #f1c40f 100%);
}

.stat-icon.purple {
  background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
}

.period-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}

.period-selector .label {
  font-weight: 500;
}

.chart-card {
  margin-bottom: 20px;
}
</style>