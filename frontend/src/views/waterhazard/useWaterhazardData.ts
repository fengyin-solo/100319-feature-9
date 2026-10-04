import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

export type WaterRow = Record<string, string | number | null>

export interface WaterSummary {
  total: number
  status_counts: Record<string, number>
  max_flow: number | null
}

/** 水害筛选口径（列表页与日报页共用），参数键与后端 query 保持一致。 */
export const FILTER_KEYS = ['region', 'date_start', 'date_end', 'flow_min', 'flow_max', 'status'] as const
export type FilterKey = (typeof FILTER_KEYS)[number]
export type Filters = Record<FilterKey, string>

export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

const EMPTY_FILTERS: Filters = {
  region: '',
  date_start: '',
  date_end: '',
  flow_min: '',
  flow_max: '',
  status: '',
}

/** 把一组筛选/翻页状态序列化成 query（空值不带进 URL，链接保持干净）。 */
export function toQuery(filters: Filters, page: number, size: number): Record<string, string> {
  const query: Record<string, string> = {}
  for (const key of FILTER_KEYS) {
    const value = filters[key].trim()
    if (value) query[key] = value
  }
  if (page > 1) query.page = String(page)
  if (size !== 20) query.size = String(size)
  return query
}

function readRoute(routeQuery: Record<string, unknown>): { filters: Filters; page: number; size: number } {
  const filters: Filters = { ...EMPTY_FILTERS }
  for (const key of FILTER_KEYS) {
    const raw = routeQuery[key]
    if (typeof raw === 'string') filters[key] = raw
  }
  const page = Math.max(1, Number(routeQuery.page) || 1)
  const size = Number(routeQuery.size) || 20
  return { filters, page, size: PAGE_SIZE_OPTIONS.includes(size) ? size : 20 }
}

/**
 * 提交前的本地口径校验：区间写反当场说明（返回 warning），
 * 调用方据此短路请求，按空结果渲染，绝不让全表数据漏出来。
 */
export function validateFilters(filters: Filters): string {
  const problems: string[] = []
  const min = Number(filters.flow_min)
  const max = Number(filters.flow_max)
  if (filters.flow_min.trim() !== '' && Number.isNaN(min)) problems.push('涌水量下限必须是数字')
  if (filters.flow_max.trim() !== '' && Number.isNaN(max)) problems.push('涌水量上限必须是数字')
  if (filters.flow_min.trim() && filters.flow_max.trim() && !Number.isNaN(min) && !Number.isNaN(max) && min > max) {
    problems.push(`涌水量区间写反了：下限 ${filters.flow_min.trim()} 大于上限 ${filters.flow_max.trim()}，请调换后再查`)
  }
  if (filters.date_start && filters.date_end && filters.date_start > filters.date_end) {
    problems.push(`监测日期区间写反了：开始日期 ${filters.date_start} 晚于结束日期 ${filters.date_end}，请调换后再查`)
  }
  return problems.join('；')
}

/**
 * 水害列表 / 日报共用的数据状态：
 * - 条件与翻页全部落在路由 query 上：翻页留住、从日报带回、刷新或重新进入仍是同一组；
 * - 区间写反由前端当场短路 + 后端兜底，两侧都是空结果加提示（不会展示全表）。
 */
export function useWaterhazardData(endpoint: string) {
  const route = useRoute()
  const router = useRouter()

  const filters = reactive<Filters>({ ...EMPTY_FILTERS })
  const page = ref(1)
  const size = ref(20)

  const rows = ref<WaterRow[]>([])
  const total = ref(0)
  const summary = ref<WaterSummary | null>(null)
  const warning = ref('')
  const errorMessage = ref('')
  const loading = ref(false)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

  function syncFromRoute() {
    const state = readRoute(route.query as Record<string, unknown>)
    Object.assign(filters, state.filters)
    page.value = state.page
    size.value = state.size
  }

  async function reload() {
    errorMessage.value = ''
    // 区间写反/格式不对：当场说明并按空结果渲染，请求都不发，更不可能捞全表。
    const localWarning = validateFilters(filters)
    if (localWarning) {
      warning.value = localWarning
      rows.value = []
      total.value = 0
      summary.value = { total: 0, status_counts: {}, max_flow: null }
      return
    }
    warning.value = ''
    const params = new URLSearchParams(toQuery(filters, page.value, size.value))
    loading.value = true
    try {
      const response = await request(`${endpoint}?${params.toString()}`)
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.detail || '水文监测列表读取失败')
      }
      rows.value = payload.items ?? []
      // 总数严格取后端统计值（筛选后、分页前），不允许用当前页条数冒充。
      total.value = payload.total ?? 0
      summary.value = payload.summary ?? null
      // 后端兜底校验（如手改 URL）同样落到提示条。
      warning.value = payload.warning ?? ''
    } catch (error) {
      rows.value = []
      total.value = 0
      errorMessage.value = error instanceof Error ? error.message : '水害防治列表读取失败'
    } finally {
      loading.value = false
    }
  }

  /** 替换 query（不写 history 栈）并按新状态拉数据；query 是唯一事实源。 */
  async function applyQuery(next: Record<string, string>) {
    const current = new URLSearchParams(
      Object.entries(route.query as Record<string, string>).filter(([, value]) => value),
    ).toString()
    const target = new URLSearchParams(next).toString()
    if (current === target) {
      await reload() // query 没变化时 watch 不触发，直接补一次加载
      return
    }
    await router.replace({ query: next }) // query 变化由 watch 统一触发加载
  }

  /** 提交筛选：回到第 1 页，带着新条件进 URL。 */
  function search() {
    void applyQuery(toQuery(filters, 1, size.value))
  }

  function resetFilters() {
    Object.assign(filters, EMPTY_FILTERS)
    page.value = 1
    void applyQuery(toQuery(filters, 1, size.value))
  }

  function goPage(target: number) {
    const nextPage = Math.min(Math.max(1, target), totalPages.value)
    page.value = nextPage
    void applyQuery(toQuery(filters, nextPage, size.value))
  }

  function changeSize(nextSize: number) {
    size.value = nextSize
    page.value = 1
    void applyQuery(toQuery(filters, 1, nextSize))
  }

  // 浏览器前进/后退，或另一个入口（日报）跳过来时，跟随 query 变化。
  watch(
    () => route.query,
    () => {
      syncFromRoute()
      void reload()
    },
    { deep: true },
  )

  // 首次进入：用当前 URL 还原上次的条件与页码。
  syncFromRoute()

  return {
    endpoint,
    filters,
    page,
    size,
    rows,
    total,
    totalPages,
    summary,
    warning,
    errorMessage,
    loading,
    reload,
    search,
    resetFilters,
    goPage,
    changeSize,
  }
}
