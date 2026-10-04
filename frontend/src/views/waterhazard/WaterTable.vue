<template>
  <table class="data-table">
    <thead>
      <tr>
        <th v-for="column in props.columns" :key="column">{{ column }}</th>
        <th v-if="props.showActions">可执行动作</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="row in props.rows" :key="String(row.id)">
        <td v-for="column in props.columns" :key="column">{{ formatCell(row, column) }}</td>
        <td v-if="props.showActions" class="row-actions">
          <button
            v-for="action in props.actions"
            :key="action"
            class="link"
            type="button"
            @click="emit('action', action, row)"
          >
            {{ action }}
          </button>
        </td>
      </tr>
      <tr v-if="!props.rows.length">
        <td :colspan="props.columns.length + (props.showActions ? 1 : 0)" class="empty-state">
          {{ props.warning ? '当前条件下没有命中记录' : props.emptyText }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
import type { WaterRow } from './useWaterhazardData'

const props = withDefaults(
  defineProps<{
    rows: WaterRow[]
    columns: string[]
    actions?: string[]
    showActions?: boolean
    emptyText?: string
    warning?: string
  }>(),
  { actions: () => [], showActions: false, emptyText: '暂无水害防治数据', warning: '' },
)

const emit = defineEmits<{
  action: [action: string, row: WaterRow]
}>()

function formatCell(row: WaterRow, column: string) {
  const value = row[column]
  if (value === null || value === undefined || value === '') return '—'
  if (column === '涌水量') return `${value} m³/h`
  return value
}
</script>
