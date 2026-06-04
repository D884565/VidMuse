<template>
  <div class="search-form">
    <el-form :model="form" inline @submit.prevent="handleSearch">
      <el-form-item
        v-for="item in fields"
        :key="item.prop"
        :label="item.label"
        :prop="item.prop"
      >
        <!-- 输入框 -->
        <el-input
          v-if="item.type === 'input'"
          v-model="form[item.prop]"
          :placeholder="item.placeholder || `请输入${item.label}`"
          :style="{ width: item.width || '200px' }"
          clearable
        />

        <!-- 选择器 -->
        <el-select
          v-if="item.type === 'select'"
          v-model="form[item.prop]"
          :placeholder="item.placeholder || `请选择${item.label}`"
          :style="{ width: item.width || '200px' }"
          clearable
        >
          <el-option
            v-for="option in item.options"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>

        <!-- 日期范围选择器 -->
        <el-date-picker
          v-if="item.type === 'daterange'"
          v-model="form[item.prop]"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :style="{ width: item.width || '300px' }"
          value-format="YYYY-MM-DD HH:mm:ss"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleSearch">
          <el-icon><search /></el-icon>
          搜索
        </el-button>
        <el-button @click="handleReset">
          <el-icon><refresh /></el-icon>
          重置
        </el-button>
        <slot name="extra" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, toRefs } from 'vue'

const props = defineProps({
  fields: {
    type: Array,
    required: true
  },
  initialForm: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['search', 'reset'])

const form = reactive({ ...props.initialForm })

const handleSearch = () => {
  emit('search', { ...form })
}

const handleReset = () => {
  Object.keys(form).forEach(key => {
    form[key] = props.initialForm[key] ?? ''
  })
  emit('reset', { ...form })
}
</script>

<style scoped>
.search-form {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
</style>