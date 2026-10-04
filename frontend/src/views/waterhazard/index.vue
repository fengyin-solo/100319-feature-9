<template>
  <section class="page" data-module="waterhazard">
    <header class="page-head">
      <div>
        <h2>水害防治管理</h2>
        <p class="page-desc">水文监测按所在区域、监测日期区间、涌水量下限组合过滤，命中结果按涌水量从大到小排列。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记水文监测</button>
        <button class="btn" type="button" @click="exportRows">导出当前筛选清单</button>
        <button class="btn" type="button" @click="goDaily">命中结果带入水害防治日报</button>
      </div>
    </header>

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
      :actions="actions"
      show-actions
      :warning="warning"
      empty-text="当前条件下暂无水文监测记录"
      @action="runAction"
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

import { request } from '@/api/client'
import WaterFilterBar from './WaterFilterBar.vue'
import WaterPagination from './WaterPagination.vue'
import WaterTable from './WaterTable.vue'
import { PAGE_SIZE_OPTIONS, toQuery, useWaterhazardData, validateFilters } from './useWaterhazardData'

const columns = ['监测编号', '所在区域', '涌水量', '水压', '水温', '水质类型', '排水能力', '监测日期', '水害状态']
const actions = ['增加监测', '突水预警', '控制确认']
const statuses = ['正常', '涌水增加', '突水危险', '已控制']
const pageSizeOptions = PAGE_SIZE_OPTIONS

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
  reload,
  search,
  resetFilters,
  goPage,
  changeSize,
} = useWaterhazardData('/api/waterhazard')

const statCards = computed(() => {
  const counts = summary.value?.status_counts ?? {}
  const maxFlow = summary.value?.max_flow
  return [
    { label: '正常区域', value: counts['正常'] ?? 0 },
    { label: '涌水增加区域', value: counts['涌水增加'] ?? 0 },
    { label: '突水危险区域', value: counts['突水危险'] ?? 0 },
    { label: '命中记录最大涌水量 (m³/h)', value: maxFlow === null || maxFlow === undefined ? '—' : maxFlow },
  ]
})

function exportRows() {
  // 区间写反时不发导出请求（后端同样会兜底返回空清单），当场说明。
  const problem = validateFilters(filters)
  if (problem) {
    warning.value = problem
    return
  }
  const params = new URLSearchParams(toQuery(filters, 1, size.value)).toString()
  window.open(`/api/waterhazard/export?${params}`, '_blank')
}

/** 把当前命中的整组条件（含页码、每页条数）带到日报入口。 */
function goDaily() {
  void router.push({ name: 'waterhazard-daily', query: { ...route.query } })
}

function openCreate() {
  errorMessage.value = '水文监测登记入口尚未接入审批流'
}

async function runAction(action: string, row: Record<string, string | number | null>) {
  errorMessage.value = ''
  try {
    const response = await request(`/api/waterhazard/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('水害防治动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '水害防治操作失败'
  }
}
</script>

<style scoped>
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
