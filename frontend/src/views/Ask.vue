<template>
  <div class="ask-wrap">
    <n-card size="small" class="chat-card">
      <template #header>💬 案例研习问答</template>
      <template #header-extra>
        <n-select v-model:value="topicId" :options="topicOptions" placeholder="全部专题检索"
                  clearable size="small" style="width: 200px" />
      </template>
      <div class="chat-list" ref="chatList">
        <n-empty v-if="!messages.length" description="向 AI 提出思政案例研习问题，回答将标注案例原文出处" style="padding: 60px 0" />
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <div class="text" v-html="renderText(m)"></div>
            <div v-if="m.sources?.length" class="sources">
              <div class="src-title">📎 引用来源（点击回跳原文）</div>
              <div v-for="(s, j) in m.sources" :key="j" class="src-item"
                   @click="jumpToChunk(s)">
                <n-tag size="tiny" type="info">[{{ j + 1 }}]</n-tag>
                《{{ s.case_title || s.filename }}》
                <span class="src-meta">{{ s.course }} · 第{{ s.page }}页{{ s.knowledge_points ? ' · ' + s.knowledge_points : '' }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="streaming" class="msg assistant">
          <div class="bubble"><div class="text">{{ streamText }}<span class="cursor">▍</span></div></div>
        </div>
      </div>
      <div class="input-bar">
        <n-input v-model:value="question" placeholder="如：张桂梅的事迹体现了怎样的人生价值追求？"
                 :disabled="streaming" @keyup.enter="send" />
        <n-button type="primary" :loading="streaming" @click="send">发 送</n-button>
      </div>
    </n-card>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api, chatStream } from '../api.js'

const message = useMessage()
const messages = ref([])
const question = ref('')
const streaming = ref(false)
const streamText = ref('')
const chatList = ref(null)
const topicId = ref(null)
const topicOptions = ref([])

function renderText(m) {
  if (m.role !== 'assistant') return escapeHtml(m.text)
  // [n] 引用渲染为角标
  return escapeHtml(m.text).replace(/\[(\d+)\]/g, (all, n) => {
    const idx = parseInt(n, 10) - 1
    if (m.sources && idx >= 0 && idx < m.sources.length) {
      return `<sup class="cite" data-i="${idx}">[${n}]</sup>`
    }
    return all
  }).replace(/\n/g, '<br/>')
}

function escapeHtml(t) {
  const d = document.createElement('div')
  d.textContent = t
  return d.innerHTML
}

function jumpToChunk(s) {
  const docId = s.doc_id
  const chunkIndex = s.chunk_index ?? 0
  window.open(`#/cases/${docId}?chunk=${chunkIndex}`, '_blank')
}

async function send() {
  const q = question.value.trim()
  if (!q || streaming.value) return
  question.value = ''
  messages.value.push({ role: 'user', text: q })
  streaming.value = true
  streamText.value = ''
  scrollToBottom()
  const reply = { role: 'assistant', text: '', sources: [] }
  let assembled = false
  try {
    await chatStream(
      { question: q, topic_id: topicId.value },
      {
        onSources: (sources) => { reply.sources = sources; scrollToBottom() },
        onDelta: (d) => {
          streamText.value += d
          scrollToBottom()
        },
        onDone: () => {
          if (!assembled) {
            assembled = true
            reply.text = streamText.value
            messages.value.push(reply)
            streamText.value = ''
          }
        },
        onRecord: () => {},
        onError: (msg) => message.error(msg),
      },
    )
    if (!assembled && streamText.value) {
      reply.text = streamText.value
      messages.value.push(reply)
      streamText.value = ''
    }
  } catch (e) {
    message.error(e.message)
    if (streamText.value) {
      reply.text = streamText.value
      messages.value.push(reply)
      streamText.value = ''
    }
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    chatList.value?.scrollTo({ top: chatList.value.scrollHeight, behavior: 'smooth' })
  })
}

onMounted(async () => {
  try {
    const topics = await api.get('/api/topics')
    topicOptions.value = topics.map(t => ({ label: t.name, value: t.id }))
  } catch { /* 忽略 */ }
})
</script>

<style scoped>
.ask-wrap { max-width: 900px; margin: 0 auto; }
.chat-card { display: flex; flex-direction: column; }
.chat-list { height: calc(100vh - 320px); min-height: 360px; overflow-y: auto; padding: 8px 4px; }
.msg { display: flex; margin-bottom: 14px; animation: bubble-in 0.3s ease both; }
@keyframes bubble-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 78%; padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.8; }
.msg.user .bubble {
  background: var(--indigo); color: #F5F1E6; border-bottom-right-radius: 2px;
  box-shadow: 0 2px 8px rgba(47, 74, 99, 0.22);
}
.msg.assistant .bubble {
  background: #FFFDF8; color: var(--ink); border-bottom-left-radius: 2px;
  border: 1px solid var(--hairline); border-left: 3px solid var(--cinnabar);
  box-shadow: 0 1px 4px rgba(33, 28, 21, 0.05);
}
.text :deep(.cite) { color: var(--cinnabar); cursor: pointer; font-weight: bold; }
.cursor { animation: blink 1s infinite; color: var(--cinnabar); }
@keyframes blink { 50% { opacity: 0; } }
.sources { margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(168, 52, 42, 0.35); }
.src-title { font-family: var(--font-kai); font-size: 12px; color: var(--cinnabar); margin-bottom: 6px; letter-spacing: 0.06em; }
.src-item { font-size: 12px; color: var(--ink-2); padding: 3px 0; cursor: pointer; }
.src-item:hover { color: var(--cinnabar); }
.src-meta { color: var(--ink-3); }
.input-bar { display: flex; gap: 10px; margin-top: 12px; }
</style>
