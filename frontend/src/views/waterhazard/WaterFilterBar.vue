<template>
  <form class="filter-bar" @submit.prevent="emit('search')">
    <label class="filter-item">
      <span>所在区域（支持模糊匹配 / 历史区域名）</span>
      <input v-model="filters.region" placeholder="如：北翼、北翼采区" />
    </label>
    <label class="filter-item">
      <span>监测开始日期</span>
      <input v-model="filters.date_start" type="date" />
    </label>
    <label class="filter-item">
      <span>监测结束日期</span>
      <input v-model="filters.date_end" type="date" />
    </label>
    <label class="filter-item">
      <span>涌水量下限（m³/h）</span>
      <input v-model.number="filters.flow_min" type="number" min="0" step="0.1" placeholder="如：60" />
    </label>
    <label class="filter-item">
      <span>涌水量上限（m³/h）</span>
      <input v-model.number="filters.flow_max" type="number" min="0" step="0.1" placeholder="选填" />
    </label>
    <label class="filter-item">
      <span>水害状态</span>
      <select v-model="filters.status">
        <option value="">全部状态</option>
        <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
      </select>
    </label>
    <button class="btn primary" type="submit">查询</button>
    <button class="btn ghost" type="button" @click="emit('reset')">重置条件</button>
  </form>
</template>

<script setup lang="ts">
import type { Filters } from './useWaterhazardData'

defineProps<{ filters: Filters; statuses: string[] }>()
const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>
