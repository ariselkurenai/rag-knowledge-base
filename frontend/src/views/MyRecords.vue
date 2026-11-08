<template>
  <div>
    <n-card title="我的研习记录" size="small">
      <n-spin :show="loading">
        <n-empty v-if="!records.length" description="暂无记录，去研习问答页提问吧" style="padding: 40px 0" />
        <n-collapse v-else>
          <n-collapse-item v-for="r in records" :key="r.id" :name="r.id">
            <template #header>
              <n-space align="center">
                <n-tag size="small" :type="typeOf(r.record_type)">
                  {{ r.record_type === 'guide_q' ? '引导问题' : '研习答疑' }}
                </n-tag>
                <span class="q">{{ r.question }}</span>
              </n-space>
            </template>
            <template #header-extra>
              <n-tag size="small" :bordered="false" :type="statusType(r.status)">{{ statusLabel(r.status) }}</n-tag>
              <span class="time">{{ r.created_at?.slice(0, 16).replace('T', ' ') }}</span>
            </template>
            <div v-if="r.teacher_comment" class="comment">
              <n-alert type="warning" :bordered="false">教师批注：{{ r.teacher_comment }}</n-alert>
            </div>
            <div v-if="r.status === 'rejected' && r.reject_reason" class="comment">
              <n-alert type="error" :bordered="false">驳回理由：{{ r.reject_reason }}</n-alert>
            </div>
            <div class="answer">{{ r.final_content || r.ai_content }}</div>
            <div v-if="r.status === 'corrected'" class="hint">（此回答已经教师修正）</div>
          </n-collapse-item>
        </n-collapse>
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const records = ref([])
const loading = ref(false)

const typeOf = (t) => (t === 'guide_q' ? 'success' : 'info')
const statusType = (s) => ({ pending: 'default', corrected: 'warning', annotated: 'info', rejected: 'error' }[s] || 'default')
const statusLabel = (s) => ({ pending: '待审核', corrected: '已修正', annotated: '已批注', rejected: '已驳回' }[s] || s)

onMounted(async () => {
  loading.value = true
  try { records.value = await api.get('/api/chat/my-records') }
  catch { records.value = [] }
  finally { loading.value = false }
})
</script>

<style scoped>
.q { font-size: 13px; }
.time { font-size: 12px; color: #9ca3af; margin-left: 8px; }
.comment { margin-bottom: 10px; }
.answer { font-size: 14px; line-height: 1.9; white-space: pre-wrap; background: #f9fafb; padding: 12px; border-radius: 6px; }
.hint { font-size: 12px; color: #9ca3af; margin-top: 6px; }
</style>
