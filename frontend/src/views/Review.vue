<template>
  <div>
    <n-space style="margin-bottom: 12px">
      <n-radio-group v-model:value="statusFilter" size="small" @update:value="load">
        <n-radio-button value="">全部</n-radio-button>
        <n-radio-button value="pending">待审核</n-radio-button>
        <n-radio-button value="corrected">已修正</n-radio-button>
        <n-radio-button value="annotated">已批注</n-radio-button>
      </n-radio-group>
      <n-tag round type="info">共 {{ records.length }} 条</n-tag>
    </n-space>

    <n-spin :show="loading">
      <n-empty v-if="!records.length" description="暂无待审内容" style="padding: 40px 0" />
      <n-card v-for="r in records" :key="r.id" size="small" style="margin-bottom: 12px">
        <template #header>
          <n-space align="center">
            <n-tag size="small" :type="r.record_type === 'guide_q' ? 'success' : 'info'">
              {{ r.record_type === 'guide_q' ? '引导问题' : '研习答疑' }}
            </n-tag>
            <span class="q">{{ r.question }}</span>
          </n-space>
        </template>
        <template #header-extra>
          <n-tag size="small" :type="statusType(r.status)">{{ statusLabel(r.status) }}</n-tag>
        </template>

        <div class="ai-content">{{ r.final_content || r.ai_content }}</div>
        <div v-if="r.status !== 'pending' && r.final_content" class="diff-hint">
          <n-alert type="warning" :bordered="false" closable>
            此内容已经教师修正，原始 AI 输出见审核日志
          </n-alert>
        </div>

        <n-space style="margin-top: 12px" v-if="r.status === 'pending'">
          <n-button size="small" type="primary" @click="openEdit(r)">✏️ 修改内容</n-button>
          <n-button size="small" type="info" @click="openComment(r)">💬 补充批注</n-button>
        </n-space>
        <n-space style="margin-top: 12px" v-else>
          <n-button size="tiny" @click="openEdit(r)">再次修改</n-button>
          <n-button size="tiny" @click="openComment(r)">追加批注</n-button>
        </n-space>

        <n-collapse style="margin-top: 10px" v-if="r.logs?.length">
          <n-collapse-item :name="r.id" title="📜 审核留痕">
            <div v-for="(log, i) in r.logs" :key="i" class="log-item">
              <n-tag size="tiny" :bordered="false">{{ actionLabel(log.action) }}</n-tag>
              <span class="log-time">{{ log.created_at?.slice(0, 16).replace('T', ' ') }}</span>
              <div v-if="log.content_before" class="log-text">改动前：{{ log.content_before }}</div>
              <div v-if="log.content_after" class="log-text">改动后：{{ log.content_after }}</div>
            </div>
          </n-collapse-item>
        </n-collapse>
      </n-card>
    </n-spin>

    <!-- 修改内容 -->
    <n-modal v-model:show="showEdit" preset="dialog" title="修改 AI 生成内容" style="width: 640px">
      <n-input v-model:value="editText" type="textarea" :rows="12" />
      <template #action>
        <n-button @click="showEdit = false">取消</n-button>
        <n-button type="primary" :loading="acting" @click="saveEdit">保存修改（留痕）</n-button>
      </template>
    </n-modal>

    <!-- 批注 -->
    <n-modal v-model:show="showText" preset="dialog" :title="textTitle" style="width: 560px">
      <n-input v-model:value="textInput" type="textarea" :rows="4"
               placeholder="填写教学批注，学生端可见" />
      <template #action>
        <n-button @click="showText = false">取消</n-button>
        <n-button type="primary" :loading="acting" @click="saveTextAction">确认（留痕）</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api.js'

const message = useMessage()
const records = ref([])
const loading = ref(false)
const statusFilter = ref('pending')

const showEdit = ref(false)
const editText = ref('')
const currentRecord = ref(null)

const showText = ref(false)
const textInput = ref('')
const textTitle = ref('')
const acting = ref(false)

const statusType = (s) => ({ pending: 'default', corrected: 'warning', annotated: 'info' }[s] || 'default')
const statusLabel = (s) => ({ pending: '待审核', corrected: '已修正', annotated: '已批注' }[s] || s)
const actionLabel = (a) => ({ edit: '修改', comment: '批注' }[a] || a)

async function load() {
  loading.value = true
  try {
    const p = statusFilter.value ? `?status=${statusFilter.value}` : ''
    records.value = await api.get('/api/review/records' + p)
  } catch { records.value = [] } finally { loading.value = false }
}

function openEdit(r) {
  currentRecord.value = r
  editText.value = r.final_content || r.ai_content
  showEdit.value = true
}

async function saveEdit() {
  acting.value = true
  try {
    await api.put(`/api/review/records/${currentRecord.value.id}`, { content: editText.value })
    message.success('修改已保存并留痕')
    showEdit.value = false
    load()
  } catch (e) { message.error(e.message) } finally { acting.value = false }
}

function openComment(r) {
  currentRecord.value = r
  textTitle.value = '💬 补充批注'
  textInput.value = ''
  showText.value = true
}

async function saveTextAction() {
  if (!textInput.value.trim()) return message.warning('请填写内容')
  acting.value = true
  const r = currentRecord.value
  try {
    await api.post(`/api/review/records/${r.id}/comment`, { comment: textInput.value })
    message.success('批注已保存并留痕')
    showText.value = false
    load()
  } catch (e) { message.error(e.message) } finally { acting.value = false }
}

onMounted(load)
</script>

<style scoped>
.q { font-family: var(--font-display); font-size: 14px; font-weight: 700; }
.ai-content {
  font-size: 14px; line-height: 1.9; white-space: pre-wrap;
  background: #FFFDF8; color: var(--ink);
  padding: 12px 14px; border-radius: 4px;
  border: 1px solid var(--hairline); border-left: 3px solid var(--indigo);
}
.diff-hint { margin-top: 8px; }
.log-item { padding: 8px 0; border-bottom: 1px dashed var(--hairline); }
.log-time { font-size: 12px; color: var(--ink-3); margin-left: 8px; }
.log-text { font-size: 13px; color: var(--ink-2); margin-top: 4px; white-space: pre-wrap; }
</style>
