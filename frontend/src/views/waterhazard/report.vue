<template>
  <section class="page" data-module="waterhazard-daily-report">
    <header class="page-head">
      <div>
        <h2>水害防治日报</h2>
        <p class="page-desc">按水害防治列表保存的筛选条件生成，与列表页读到的是同一组结果。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/waterhazard">返回水文监测列表</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">生成日期</span>
        <strong class="stat-value">{{ report?.generated_on ?? '—' }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">命中记录</span>
        <strong class="stat-value">{{ report?.total ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">最大涌水量 (m³/h)</span>
        <strong class="stat-value">{{ report?.max_inflow ?? '—' }}</strong>
      </article>
    </div>

    <p class="report-filters">筛选条件：{{ filterSummary }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">
            {{ column === '涌水量' ? '涌水量 ↓' : column }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!items.length">
          <td :colspan="columns.length" class="empty-state">当前条件下没有水文监测记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ report?.total ?? 0 }} 条水文监测记录</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface DailyReport {
  generated_on: string
  total: number
  max_inflow: number | null
  filters: Record<string, string>
  items: Row[]
}

const ENDPOINT = '/api/waterhazard'
const STORAGE_KEY = 'waterhazard:filters'
const columns = ["监测编号", "所在区域", "监测日期", "涌水量", "水压", "水温", "水质类型", "排水能力", "水害状态"]

const report = ref<DailyReport | null>(null)
const items = ref<Row[]>([])
const errorMessage = ref('')

const filterSummary = computed(() => {
  const applied = report.value?.filters ?? {}
  const parts = Object.entries(applied).map(([label, value]) => `${label} ${value}`)
  return parts.length ? parts.join('；') : '未设置（全部记录）'
})

function savedParams(): URLSearchParams {
  // 与列表页读同一份保存的条件，保证两个入口结果一致
  let saved: Record<string, unknown> = {}
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') as Record<string, unknown>
  } catch {
    saved = {}
  }
  const params = new URLSearchParams()
  const mapping: Record<string, string> = {
    keyword: 'keyword',
    region: 'region',
    dateFrom: 'date_from',
    dateTo: 'date_to',
    inflowMin: 'inflow_min',
    inflowMax: 'inflow_max',
    status: 'status',
  }
  for (const [key, param] of Object.entries(mapping)) {
    const value = String(saved[key] ?? '').trim()
    if (value) {
      params.set(param, value)
    }
  }
  return params
}

async function loadReport() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/daily-report?${savedParams().toString()}`)
    const payload = (await response.json().catch(() => ({}))) as Partial<DailyReport> & { detail?: string }
    if (!response.ok) {
      report.value = null
      items.value = []
      errorMessage.value = payload.detail || '查询条件不合法，请回列表页调整后重试'
      return
    }
    report.value = payload as DailyReport
    items.value = payload.items ?? []
  } catch (error) {
    report.value = null
    items.value = []
    errorMessage.value = error instanceof Error ? error.message : '水害防治日报读取失败'
  }
}

onMounted(loadReport)
</script>
