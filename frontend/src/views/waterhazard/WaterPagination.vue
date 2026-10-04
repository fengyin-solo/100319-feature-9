<template>
  <div class="water-pager">
    <label class="pager-size">
      每页
      <select :value="props.size" @change="onSizeChange">
        <option v-for="option in props.sizeOptions" :key="option" :value="option">{{ option }} 条</option>
      </select>
    </label>
    <div class="pager-nav">
      <button class="btn" type="button" :disabled="props.page <= 1" @click="emit('change-page', props.page - 1)">
        上一页
      </button>
      <span class="pager-indicator">第 {{ props.page }} / {{ totalPages }} 页</span>
      <button
        class="btn"
        type="button"
        :disabled="props.page >= totalPages"
        @click="emit('change-page', props.page + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    page: number
    size: number
    total: number
    sizeOptions?: number[]
  }>(),
  { sizeOptions: () => [10, 20, 50, 100] },
)

const emit = defineEmits<{
  'change-page': [page: number]
  'change-size': [size: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.size)))

function onSizeChange(event: Event) {
  emit('change-size', Number((event.target as HTMLSelectElement).value))
}
</script>

<style scoped>
.water-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}
.pager-size {
  font-size: 12px;
  color: var(--muted);
}
.pager-size select {
  margin: 0 4px;
}
.pager-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pager-nav .btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.pager-indicator {
  font-size: 12px;
  color: var(--muted);
}
</style>
