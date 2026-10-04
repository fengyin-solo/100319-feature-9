<template>
  <section class="page" data-module="waterhazard-daily">
    <header class="page-head">
      <div>
        <h2>水害防治日报</h2>
        <p class="page-desc">
          日报直接采用水害防治列表的筛选口径与命中结果，两个入口看到的条数、排序、汇总完全一致。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="backToList">带当前条件回到列表处理</button>
      </div>
    </header>

    <article class="report-head">
      <div class="report-meta">
        <span>报告生成日期：{{ today }}</span>
        <span>命中记录：<strong>{{ total }}</strong> 条</span>
        <span>最大涌水量：<strong>{{ summary?.max_flow ?? '—' }}</strong> m³/h</span>
      </div>
      <ul class="report-chips">
        <li v-for="chip in activeChips" :key="chip.label" class="report-chip">{{ chip.label }}：{{ chip.value }}</li>
        <li v-if="!activeChips.length" class="report-chip muted">未设置筛选条件（全量水文监测）</li>
      </ul>
    </article>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <WaterFilterBar :filters="filters" :statuses="statuses" @search="search" @reset="resetFilters" />

    <p v-if="warning" class="filter-warning">{{ warning }}</p>

    <WaterTable
      :rows="rows"
      :columns="columns"
      :warning="warning"
      empty-text="当前条件下日报没有可收录的水文监测记录"
    />

    <footer class="page-foot">
      <span>共 {{ total }} 条命中记录（按涌水量从大到小排序）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <WaterPagination
      :page="page"
      :size="size"
      :total="total"
      :size-options="pageSizeOptions"
      @change-page="goPage"
      @change-size="changeSize"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WaterFilterBar from './WaterFilterBar.vue'
import WaterPagination from './WaterPagination.vue'
import WaterTable from './WaterTable.vue'
import { PAGE_SIZE_OPTIONS, useWaterhazardData } from './useWaterhazardData'

const columns = ['监测编号', '所在区域', '涌水量', '水压', '水温', '水质类型', '排水能力', '监测日期', '水害状态']
const statuses = ['正常', '涌水增加', '突水危险', '已控制']
const pageSizeOptions = PAGE_SIZE_OPTIONS
const today = new Date().toISOString().slice(0, 10)

const route = useRoute()
const router = useRouter()

const {
  filters,
  page,
  size,
  rows,
  total,
  summary,
  warning,
  errorMessage,
  search,
  resetFilters,
  goPage,
  changeSize,
} = useWaterhazardData('/api/waterhazard/daily-report')

const statCards = computed(() => {
  const counts = summary.value?.status_counts ?? {}
  return [
    { label: '正常区域', value: counts['正常'] ?? 0 },
    { label: '涌水增加区域', value: counts['涌水增加'] ?? 0 },
    { label: '突水危险区域', value: counts['突水危险'] ?? 0 },
    { label: '已控制区域', value: counts['已控制'] ?? 0 },
  ]
})

const FILTER_LABELS: Record<string, string> = {
  region: '所在区域',
  date_start: '开始日期',
  date_end: '结束日期',
  flow_min: '涌水量下限 (m³/h)',
  flow_max: '涌水量上限 (m³/h)',
  status: '水害状态',
}

const activeChips = computed(() =>
  Object.entries(filters)
    .filter(([, value]) => value.trim())
    .map(([key, value]) => ({ label: FILTER_LABELS[key] ?? key, value })),
)

function backToList() {
  void router.push({ name: 'waterhazard', query: { ...route.query } })
}
</script>

<style scoped>
.report-head {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.report-meta {
  display: flex;
  gap: 18px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 8px;
}
.report-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.report-chip {
  font-size: 12px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  border-radius: 999px;
  padding: 2px 10px;
}
.report-chip.muted {
  background: #f8fafc;
  border-color: var(--border);
  color: var(--muted);
}
.filter-warning {
  margin: 0 0 10px;
  padding: 8px 12px;
  border: 1px solid #f0b429;
  background: #fffbeb;
  color: #92400e;
  border-radius: 6px;
  font-size: 13px;
}
</style>
