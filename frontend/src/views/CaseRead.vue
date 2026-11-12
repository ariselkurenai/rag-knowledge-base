<template>
  <div v-if="info">
    <n-page-header @back="$router.push('/cases')" style="margin-bottom: 16px">
      <template #title>{{ info.case?.case_title || info.filename }}</template>
      <template #avatar>📖</template>
    </n-page-header>

    <n-card size="small" style="margin-bottom: 16px" v-if="info.case">
      <n-space size="small">
        <n-tag type="info" :bordered="false">{{ info.case.course }}</n-tag>
        <n-tag v-if="info.case.case_type" :bordered="false">{{ info.case.case_type }}</n-tag>
        <n-tag v-if="info.case.knowledge_points" type="success" :bordered="false">
          {{ info.case.knowledge_points }}
        </n-tag>
        <n-tag v-if="info.case.related_theory" type="warning" :bordered="false">
          {{ info.case.related_theory }}
        </n-tag>
      </n-space>
    </n-card>

    <n-card title="案例原文" size="small">
      <div v-for="c in info.chunks" :key="c.chunk_id" class="chunk"
           :class="{ highlight: c.index === highlight }">
        <div class="chunk-page">第 {{ c.page }} 页 · 片段 {{ c.index + 1 }}</div>
        <div class="chunk-text">{{ c.content }}</div>
      </div>
    </n-card>

    <n-card title="课堂研习引导问题" size="small" style="margin-top: 16px"
            v-if="['teacher', 'admin'].includes(role)">
      <template #header-extra>
        <n-button size="small" type="primary" :loading="generating" @click="generate">
          生成引导问题
        </n-button>
      </template>
      <n-empty v-if="!guideContent" description="点击上方按钮，AI 将为该案例生成课堂研习引导问题" />
      <div v-else class="guide">
        <n-alert type="success" :bordered="false">已生成（记录 #{{ guideRecordId }}），可在审核工作台修改与批注</n-alert>
        <pre class="guide-pre">{{ guideContent }}</pre>
      </div>
    </n-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api, auth } from '../api.js'

const route = useRoute()
const message = useMessage()
const info = ref(null)
const highlight = ref(-1)
const generating = ref(false)
const guideContent = ref('')
const guideRecordId = ref(null)
const role = auth.user?.role

async function generate() {
  generating.value = true
  try {
    const data = await api.post('/api/review/guide-questions', {
      doc_id: route.params.docId, n: 5,
    })
    guideContent.value = data.content
    guideRecordId.value = data.record_id
    message.success('引导问题已生成')
  } catch (e) { message.error(e.message) } finally { generating.value = false }
}

onMounted(async () => {
  try {
    info.value = await api.get(`/api/documents/${route.params.docId}/content`)
    const idx = parseInt(route.query.chunk || '-1', 10)
    if (idx >= 0) {
      highlight.value = idx
      setTimeout(() => {
        document.querySelectorAll('.chunk')[idx]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 200)
    }
  } catch (e) { message.error(e.message) }
})
</script>

<style scoped>
.chunk { padding: 10px 0; border-bottom: 1px dashed var(--hairline); transition: background 0.5s, box-shadow 0.4s; }
.chunk.highlight {
  background: var(--cinnabar-wash); border-radius: 4px; padding: 10px 12px;
  border-left: 3px solid var(--cinnabar);
  box-shadow: 0 2px 10px rgba(168, 52, 42, 0.14);
}
.chunk-page { font-family: var(--font-kai); font-size: 12px; color: var(--cinnabar); margin-bottom: 4px; letter-spacing: 0.05em; }
.chunk-text { font-size: 14px; line-height: 1.9; white-space: pre-wrap; }
.guide-pre {
  white-space: pre-wrap; font-family: var(--font-kai); font-size: 15px;
  line-height: 2.0; margin: 12px 0 0; color: var(--ink);
}
</style>
