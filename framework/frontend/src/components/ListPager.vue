<template>
  <nav v-if="total > 0" class="list-pager" aria-label="列表分页">
    <span>每页 {{ LIST_PAGE_SIZE }} 条</span>
    <el-pagination background layout="total, prev, pager, next" :pager-count="5" :current-page="page" :page-size="LIST_PAGE_SIZE" :total="total" @current-change="$emit('change', $event)"/>
  </nav>
</template>
<script setup>
import { LIST_PAGE_SIZE } from '@/domain/pagination'
defineProps({ page: { type: Number, default: 1 }, total: { type: Number, required: true } })
defineEmits(['change'])
</script>
<style scoped>
.list-pager{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;min-height:52px;margin-top:22px;color:#586f82;font-size:14px}.list-pager :deep(.el-pagination){max-width:100%;flex-wrap:wrap}.list-pager :deep(.el-pager){max-width:100%;flex-wrap:wrap}
</style>
