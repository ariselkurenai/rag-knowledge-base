<template>
  <div>
    <n-tabs v-model:value="tab" type="line">
      <!-- 案例上传与元数据 -->
      <n-tab-pane name="docs" tab="案例管理">
        <n-space style="margin-bottom: 12px">
          <n-upload :custom-request="doUpload" :show-file-list="false" multiple
                    accept=".pdf,.docx,.txt,.md">
            <n-button type="primary">📤 上传案例文档（可多选）</n-button>
          </n-upload>
          <n-select v-model:value="topicId" :options="topicOptions" placeholder="上传时归属专题"
                    clearable style="width: 220px" />
        </n-space>
        <n-data-table :columns="docCols" :data="docs" :loading="loading" size="small" />
      </n-tab-pane>

      <!-- 专题管理 -->
      <n-tab-pane name="topics" tab="专题管理">
        <n-space style="margin-bottom: 12px">
          <n-input v-model:value="newTopic" placeholder="新专题名称，如：思想道德与法治" style="width: 300px" />
          <n-button type="primary" @click="addTopic">新建专题</n-button>
        </n-space>
        <n-data-table :columns="topicCols" :data="topics" size="small" />
      </n-tab-pane>
    </n-tabs>

    <!-- 元数据编辑弹窗 -->
    <n-modal v-model:show="showEdit" preset="dialog" title="编辑案例元数据" style="width: 520px">
      <n-form v-if="editing" label-placement="left" label-width="80" size="small">
        <n-form-item label="案例名"><n-input v-model:value="editing.case_title" /></n-form-item>
        <n-form-item label="课程"><n-input v-model:value="editing.course" /></n-form-item>
        <n-form-item label="类型"><n-input v-model:value="editing.case_type" /></n-form-item>
        <n-form-item label="知识点"><n-input v-model:value="editing.knowledge_points" /></n-form-item>
        <n-form-item label="理论关联"><n-input v-model:value="editing.related_theory" /></n-form-item>
        <n-form-item label="归属专题">
          <n-select v-model:value="editing.topic_id" :options="topicOptions" clearable placeholder="不归属" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="showEdit = false">取消</n-button>
        <n-button type="primary" :loading="saving" @click="saveEdit">保存</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NSpace, NTag, useDialog, useMessage } from 'naive-ui'
import { api } from '../api.js'

const message = useMessage()
const dialog = useDialog()
const tab = ref('docs')
const docs = ref([])
const topics = ref([])
const topicOptions = ref([])
const topicId = ref(null)
const newTopic = ref('')
const loading = ref(false)
const showEdit = ref(false)
const editing = ref(null)
const saving = ref(false)

async function loadAll() {
  loading.value = true
  try {
    docs.value = await api.get('/api/documents')
    topics.value = await api.get('/api/topics')
    topicOptions.value = topics.value.map(t => ({ label: t.name, value: t.id }))
  } finally { loading.value = false }
}

async function doUpload({ file }) {
  const form = new FormData()
  form.append('file', file.file)
  if (topicId.value) form.append('topic_id', topicId.value)
  try {
    const r = await api.upload('/api/documents', form)
    message.success(`《${r.case_title || file.name}》入库成功：${r.message}`)
    loadAll()
  } catch (e) { message.error(e.message) }
}

const docCols = [
  { title: '案例', key: 'case_title', render: (r) => r.case?.case_title || r.filename },
  { title: '课程', key: 'course', render: (r) => r.case?.course || '—' },
  { title: '专题', render: (r) => r.topic_name ? h(NTag, { size: 'small', bordered: false }, { default: () => r.topic_name }) : '—' },
  { title: '切片', key: 'chunks', width: 60 },
  {
    title: '操作', width: 200, render: (r) => h(NSpace, { size: 'small' }, { default: () => [
      h(NButton, { size: 'tiny', onClick: () => openEdit(r) }, { default: () => '编辑' }),
      h(NButton, { size: 'tiny', type: 'error', ghost: true, onClick: () => delDoc(r) }, { default: () => '删除' }),
    ] }),
  },
]

function openEdit(r) {
  editing.value = {
    doc_id: r.doc_id,
    case_title: r.case?.case_title || '', course: r.case?.course || '',
    case_type: r.case?.case_type || '', knowledge_points: r.case?.knowledge_points || '',
    related_theory: r.case?.related_theory || '', topic_id: r.topic_id ?? null,
  }
  showEdit.value = true
}

async function saveEdit() {
  saving.value = true
  const e = editing.value
  try {
    await api.put(`/api/documents/${e.doc_id}/meta`, e)
    message.success('元数据已更新（已留痕）')
    showEdit.value = false
    loadAll()
  } catch (err) { message.error(err.message) } finally { saving.value = false }
}

function delDoc(r) {
  dialog.warning({
    title: '删除案例',
    content: `确定删除《${r.case?.case_title || r.filename}》？切片与索引将一并移除。`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.del(`/api/documents/${r.doc_id}`)
        message.success('已删除')
        loadAll()
      } catch (e) { message.error(e.message) }
    },
  })
}

async function addTopic() {
  if (!newTopic.value.trim()) return
  try {
    await api.post('/api/topics', { name: newTopic.value.trim() })
    message.success('专题已创建')
    newTopic.value = ''
    loadAll()
  } catch (e) { message.error(e.message) }
}

const topicCols = [
  { title: 'ID', key: 'id', width: 50 },
  { title: '专题名称', key: 'name' },
  { title: '案例数', key: 'case_count', width: 80 },
]

onMounted(loadAll)
</script>
