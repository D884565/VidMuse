<template>
  <div class="common-table">
    <el-table
      v-loading="loading"
      :data="tableData"
      :border="border"
      :stripe="stripe"
      :height="height"
      v-bind="$attrs"
    >
      <template v-for="column in columns" :key="column.prop">
        <el-table-column
          v-bind="column"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :align="column.align || 'center'"
        >
          <template #default="scope">
            <slot v-if="column.slot" :name="column.slot" v-bind="scope" />
            <span v-else>
              {{ column.formatter ? column.formatter(scope.row[column.prop], scope.row) : scope.row[column.prop] }}
            </span>
          </template>
        </el-table-column>
      </template>

      <!-- 操作列 -->
      <el-table-column
        v-if="showAction"
        label="操作"
        width="120"
        align="center"
        fixed="right"
      >
        <template #default="scope">
          <slot name="action" v-bind="scope" />
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrapper" v-if="showPagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  columns: {
    type: Array,
    required: true
  },
  tableData: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  border: {
    type: Boolean,
    default: true
  },
  stripe: {
    type: Boolean,
    default: true
  },
  height: {
    type: [String, Number],
    default: 'auto'
  },
  showAction: {
    type: Boolean,
    default: true
  },
  showPagination: {
    type: Boolean,
    default: true
  },
  pagination: {
    type: Object,
    default: () => ({
      page: 1,
      page_size: 20,
      total: 0
    })
  }
})

const emit = defineEmits(['update:pagination', 'query'])

const handleSizeChange = (size) => {
  emit('update:pagination', {
    ...props.pagination,
    page_size: size,
    page: 1
  })
  emit('query')
}

const handleCurrentChange = (page) => {
  emit('update:pagination', {
    ...props.pagination,
    page
  })
  emit('query')
}
</script>

<style scoped>
.common-table {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>