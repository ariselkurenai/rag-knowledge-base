<template>
  <div>
    <n-card title="案例语义检索" size="small">
      <n-space style="width: 100%">
        <n-input v-model:value="q" placeholder="输入关键词或问题，如：人生价值、脱贫攻坚"
                 style="width: 480px" clearable @keyup.enter="doSearch" />
        <n-select v-model:value="topicId" :options="topicOptions" placeholder="全部专题"
                  clearable style="width: 220px" />
        <n-button type="primary" :loading="loading" @click="doSearch">检 索</n-button>
      </n-space>
    </n-card>

    <n-spin :show="loading" style="margin-top: 16px">
      <n-empty v-if="searched && !hits.length" description="没有命中案例" style="padding: 40px 0" />
      <n-card v-for="h in hits" :key="h.chunk_id" size="small" style="margin-bottom: 12px" hoverable>
        <template #header>
          《{{ h.case_title || h.filename }}》
          <n-tag size="small" type="info" :bordered="false" style="margin-left: 8px">{{ h.course }}</n-tag>
        </template>
        <template #header-extra>
          <n-tag size="small" :bordered="false">相关度 {{ h.score }}</n-tag>
        </template>
        <div class="content">{{ h.content }}</div>
        <template #action>
          <n-space justify="space-between">
            <span class="meta">第 {{ h.page }} 页 · {{ h.knowledge_points || '—' }}</span>
            <n-button size="tiny" tag="a" :href="`#/cases/${h.doc_id}`" type="primary" ghost>
              查看案例原文
            </n-button>
          </n-space>
        </template>
      </n-card>
    </n-spin>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'

const message = useMessage()
const q = ref('')
const topicId = ref(null)
const hits = ref([])
const loading = ref(false)
const searched = ref(false)
const topicOptions = ref([])

async function doSearch() {
  if (!q.value.trim()) return message.warning('请输入检索内容')
  loading.value = true
  searched.value = true
  try {
    const params = new URLSearchParams({ q: q.value.trim(), k: '6' })
    if (topicId.value) params.set('topic_id', topicId.value)
    const data = await api.get('/api/cases/search?' + params.toString())
    hits.value = data.hits
  } catch (e) { message.error(e.message) } finally { loading.value = false }
}

onMounted(async () => {
  try {
    const topics = await api.get('/api/topics')
    topicOptions.value = topics.map(t => ({ label: t.name, value: t.id }))
  } catch { /* 忽略 */ }
})
</script>

<style scoped>
.content { font-size: 13px; line-height: 1.8; color: #374151; }
.meta { font-size: 12px; color: #9ca3af; }
</style>
