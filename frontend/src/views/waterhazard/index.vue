<template>
  <section class="page" data-module="waterhazard">
    <header class="page-head">
      <div>
        <h2>水害防治管理</h2>
        <p class="page-desc">按所在区域、监测日期区间、涌水量区间组合过滤水文监测，命中结果按涌水量从大到小排序。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记水文监测</button>
        <button class="btn" type="button" @click="exportRows">导出水害防治清单</button>
        <RouterLink class="btn" to="/waterhazard/daily-report">水害防治日报</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">命中记录</span>
        <strong class="stat-value">{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">本页最大涌水量 (m³/h)</span>
        <strong class="stat-value">{{ pageMaxInflow }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">生效中的筛选条件</span>
        <strong class="stat-value">{{ activeFilterCount }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>监测编号</span>
        <input v-model="filters.keyword" placeholder="按监测编号检索" />
      </label>
      <label class="filter-item">
        <span>所在区域（模糊匹配）</span>
        <input v-model="filters.region" list="waterhazard-region-names" placeholder="如：东翼" />
        <datalist id="waterhazard-region-names">
          <option v-for="name in regionNames" :key="name" :value="name" />
        </datalist>
      </label>
      <label class="filter-item">
        <span>监测日期起</span>
        <input v-model="filters.dateFrom" type="date" />
      </label>
      <label class="filter-item">
        <span>监测日期止</span>
        <input v-model="filters.dateTo" type="date" />
      </label>
      <label class="filter-item">
        <span>涌水量下限 (m³/h)</span>
        <input v-model="filters.inflowMin" inputmode="decimal" placeholder="不小于" />
      </label>
      <label class="filter-item">
        <span>涌水量上限 (m³/h)</span>
        <input v-model="filters.inflowMax" inputmode="decimal" placeholder="不大于" />
      </label>
      <label class="filter-item">
        <span>水害状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn primary" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="errorMessage" class="error-text filter-error">{{ errorMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">
            {{ column === '涌水量' ? '涌水量 ↓' : column }}
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ errorMessage ? '按当前条件没有可展示的结果' : '当前条件下没有水文监测记录，可调整条件或登记水文监测' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条水文监测记录 · 第 {{ page }} / {{ pages }} 页</span>
      <div class="pager">
        <label class="pager-size">
          每页
          <select :value="size" @change="changeSize">
            <option v-for="option in pageSizes" :key="option" :value="option">{{ option }}</option>
          </select>
          条
        </label>
        <button class="btn" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <button class="btn" type="button" :disabled="page >= pages" @click="goPage(page + 1)">下一页</button>
      </div>
      <span v-if="actionMessage" class="error-text">{{ actionMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/waterhazard'
const STORAGE_KEY = 'waterhazard:filters'
const columns = ["监测编号", "所在区域", "监测日期", "涌水量", "水压", "水温", "水质类型", "排水能力", "水害状态"]
const actions = ["增加监测", "突水预警", "控制确认"]
const statuses = ["正常", "涌水增加", "突水危险", "已控制"]
const pageSizes = [10, 20, 50, 100]

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const errorMessage = ref('')
const actionMessage = ref('')
const regionNames = ref<string[]>([])

const filters = reactive({
  keyword: '',
  region: '',
  dateFrom: '',
  dateTo: '',
  inflowMin: '',
  inflowMax: '',
  status: '',
})

const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

const pageMaxInflow = computed(() => {
  const values = rows.value
    .map((row) => Number(row['涌水量']))
    .filter((value) => Number.isFinite(value))
  return values.length ? Math.max(...values) : '—'
})

const activeFilterCount = computed(() =>
  [filters.keyword, filters.region, filters.dateFrom, filters.dateTo, filters.inflowMin, filters.inflowMax, filters.status]
    .filter((value) => value.trim() !== '').length,
)

function asText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? String(value[0] ?? '') : ''
  }
  return value == null ? '' : String(value)
}

function restoreFilters() {
  // 优先地址栏里的条件（可分享、可刷新），其次本地保存的上一组条件
  const query = route.query
  let saved: Record<string, unknown>
  if (Object.keys(query).length > 0) {
    saved = { ...query }
  } else {
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') as Record<string, unknown>
    } catch {
      saved = {}
    }
  }
  filters.keyword = asText(saved.keyword)
  filters.region = asText(saved.region)
  filters.dateFrom = asText(saved.dateFrom)
  filters.dateTo = asText(saved.dateTo)
  filters.inflowMin = asText(saved.inflowMin)
  filters.inflowMax = asText(saved.inflowMax)
  filters.status = asText(saved.status)
  const savedPage = Number(asText(saved.page))
  page.value = Number.isInteger(savedPage) && savedPage > 0 ? savedPage : 1
  const savedSize = Number(asText(saved.size))
  size.value = pageSizes.includes(savedSize) ? savedSize : 20
}

function persistFilters() {
  // 条件写进地址栏与本地存储：翻页不丢，重新进来还是刚才那组条件
  const snapshot: Record<string, string> = {}
  if (filters.keyword.trim()) snapshot.keyword = filters.keyword.trim()
  if (filters.region.trim()) snapshot.region = filters.region.trim()
  if (filters.dateFrom) snapshot.dateFrom = filters.dateFrom
  if (filters.dateTo) snapshot.dateTo = filters.dateTo
  if (filters.inflowMin.trim()) snapshot.inflowMin = filters.inflowMin.trim()
  if (filters.inflowMax.trim()) snapshot.inflowMax = filters.inflowMax.trim()
  if (filters.status) snapshot.status = filters.status
  snapshot.page = String(page.value)
  snapshot.size = String(size.value)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
  void router.replace({ query: snapshot })
}

function buildParams(): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.keyword.trim()) params.set('keyword', filters.keyword.trim())
  if (filters.region.trim()) params.set('region', filters.region.trim())
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  if (filters.inflowMin.trim()) params.set('inflow_min', filters.inflowMin.trim())
  if (filters.inflowMax.trim()) params.set('inflow_max', filters.inflowMax.trim())
  if (filters.status) params.set('status', filters.status)
  return params
}

async function reload() {
  errorMessage.value = ''
  const params = buildParams()
  params.set('page', String(page.value))
  params.set('size', String(size.value))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    const payload = (await response.json().catch(() => ({}))) as {
      items?: Row[]
      total?: number
      detail?: string
    }
    if (!response.ok) {
      // 条件不合法（如涌水量区间写反）：当场说明，并按空结果展示，不把整表捞出来
      rows.value = []
      total.value = 0
      errorMessage.value = payload.detail || '查询条件不合法，请调整后重试'
      persistFilters()
      return
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    persistFilters()
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '水文监测列表读取失败'
  }
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.keyword = ''
  filters.region = ''
  filters.dateFrom = ''
  filters.dateTo = ''
  filters.inflowMin = ''
  filters.inflowMax = ''
  filters.status = ''
  page.value = 1
  size.value = 20
  localStorage.removeItem(STORAGE_KEY)
  void router.replace({ query: {} })
  void reload()
}

function goPage(target: number) {
  if (target < 1 || target > pages.value) {
    return
  }
  page.value = target
  void reload()
}

function changeSize(event: Event) {
  const next = Number((event.target as HTMLSelectElement).value)
  size.value = pageSizes.includes(next) ? next : 20
  page.value = 1
  void reload()
}

async function loadRegionNames() {
  try {
    const response = await request(`${ENDPOINT}/regions`)
    if (!response.ok) {
      return
    }
    const payload = (await response.json()) as { names?: string[] }
    regionNames.value = payload.names ?? []
  } catch {
    regionNames.value = []
  }
}

function openCreate() {
  actionMessage.value = '水文监测登记入口尚未接入审批流'
}

function exportRows() {
  const params = buildParams()
  window.open(`${ENDPOINT}/export?${params.toString()}`, '_blank')
}

async function runAction(action: string, row: Row) {
  actionMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${String(row.id)}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json().catch(() => ({}))) as { ok?: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '水害防治动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '水害防治操作失败'
  }
}

onMounted(() => {
  restoreFilters()
  void reload()
  void loadRegionNames()
})
</script>
