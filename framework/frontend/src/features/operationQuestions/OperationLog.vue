<template>
  <div class="op-log-table">
    <el-table v-if="events.length" :data="pageView.items" row-key="event_id" empty-text="尚无操作记录">
      <el-table-column prop="sequence" label="序号" width="68" class-name="op-number" />
      <el-table-column label="动作" min-width="110"><template #default="{ row }">{{ actionLabel(row.action) }}</template></el-table-column>
      <el-table-column label="功能 / 设备" min-width="125"><template #default="{ row }"><span translate="no">{{ row.target_id || buttonLabel(row.button_id) }}</span></template></el-table-column>
      <el-table-column label="执行结果" min-width="220"><template #default="{ row }"><span class="op-log-result" :class="{ rejected: !row.result?.accepted }">{{ row.result?.accepted ? '已接受' : '已拒绝' }}</span><div class="op-log-message">{{ row.result?.message || '—' }}</div></template></el-table-column>
    </el-table>
    <el-empty v-else :image-size="72" description="尚无操作记录" />
    <ListPager :page="pageView.page" :total="pageView.total" @change="page = $event" />
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import ListPager from '@/components/ListPager.vue'
import { paginate } from '@/domain/pagination'
import { actionLabel, buttonLabel } from '@/domain/operationPresentation'
import './operation.css'
const props = defineProps({ events: { type: Array, default: () => [] } })
const page = ref(1)
const pageView = computed(() => paginate(props.events, page.value))
watch(() => props.events.length, () => { if (page.value > Math.max(1, Math.ceil(props.events.length / 6))) page.value = 1 })
</script>
