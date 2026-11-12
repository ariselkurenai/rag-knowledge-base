<template>
  <div>
    <n-space align="center" style="margin-bottom: 16px">
      <n-select v-model:value="topicId" :options="topicOptions" placeholder="全部专题"
                clearable style="width: 260px" @update:value="load" />
      <n-input v-model:value="q" placeholder="搜索案例名 / 知识点" clearable style="width: 260px"
               @keyup.enter="load">
        <template #suffix>
          <n-button quaternary size="tiny" @click="load">搜索</n-button>
        </template>
      </n-input>
      <n-tag round type="info">共 {{ docs.length }} 个案例</n-tag>
    </n-space>

    <n-spin :show="loading">
      <n-empty v-if="!loading && !docs.length" description="暂无案例" style="padding: 60px 0" />
      <n-grid :cols="3" :x-gap="16" :y-gap="16">
        <n-grid-item v-for="d in docs" :key="d.doc_id">
          <n-card hoverable size="small" @click="$router.push(`/cases/${d.doc_id}`)">
            <template #header>
              <span class="case-title">{{ d.case?.case_title || d.filename }}</span>
            </template>
            <template #header-extra>
              <n-tag size="small" :type="d.topic_id === 1 ? 'success' : 'warning'" v-if="d.topic_name">
                {{ d.topic_name }}
              </n-tag>
            </template>
            <n-space size="small" style="margin-bottom: 8px">
              <n-tag size="small" type="info" :bordered="false">{{ d.case?.course || '未标注课程' }}</n-tag>
              <n-tag size="small" :bordered="false" v-if="d.case?.case_type">{{ d.case.case_type }}</n-tag>
            </n-space>
            <div class="kp" v-if="d.case?.knowledge_points">知识点：{{ d.case.knowledge_points }}</div>
            <div class="kp" v-if="d.case?.related_theory">理论关联：{{ d.case.related_theory }}</div>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-spin>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const docs = ref([])
const topics = ref([])
const topicId = ref(null)
const q = ref('')
const loading = ref(false)
const topicOptions = ref([])

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (topicId.value) params.set('topic_id', topicId.value)
    if (q.value.trim()) params.set('q', q.value.trim())
    docs.value = await api.get('/api/documents?' + params.toString())
  } catch (e) {
    docs.value = []
  } finally { loading.value = false }
}

onMounted(async () => {
  try {
    topics.value = await api.get('/api/topics')
    topicOptions.value = topics.value.map(t => ({ label: t.name, value: t.id }))
  } catch { /* 忽略 */ }
  load()
})
</script>

<style scoped>
:deep(.n-card) { transition: transform 0.2s ease, box-shadow 0.2s ease; cursor: pointer; }
:deep(.n-card:hover) { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(33, 28, 21, 0.12); }
.case-title {
  font-family: var(--font-display); font-size: 15px; font-weight: 700;
  color: var(--ink); letter-spacing: 0.02em;
}
.kp { font-size: 12px; color: var(--ink-3); margin-top: 5px; line-height: 1.7; }
.kp::before { content: ''; display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: rgba(168, 52, 42, 0.45); margin-right: 7px; vertical-align: 2px; }
</style>
