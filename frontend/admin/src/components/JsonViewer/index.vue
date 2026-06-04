<template>
  <div class="json-viewer">
    <el-button
      size="small"
      @click="showDialog = true"
      type="primary"
      plain
    >
      查看原始JSON
    </el-button>

    <el-dialog
      v-model="showDialog"
      title="原始JSON数据"
      width="800px"
      top="5vh"
    >
      <pre class="json-content"><code>{{ formattedJson }}</code></pre>
      <template #footer>
        <el-button @click="showDialog = false">关闭</el-button>
        <el-button type="primary" @click="handleCopy">
          <el-icon><copy-document /></el-icon>
          复制到剪贴板
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  data: {
    type: Object,
    required: true
  }
})

const showDialog = ref(false)

const formattedJson = computed(() => {
  return JSON.stringify(props.data, null, 2)
})

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(formattedJson.value)
    ElMessage.success('复制成功')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style scoped>
.json-content {
  max-height: 70vh;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 20px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>