// 统一 API 封装：token 注入 + 401 自动跳登录
const TOKEN_KEY = 'sizheng_token'
const USER_KEY = 'sizheng_user'

export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY) || '' },
  get user() {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') }
    catch { return null }
  },
  save(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  clear() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY) },
}

async function request(method, path, body = null, isForm = false) {
  const headers = {}
  if (auth.token) headers['Authorization'] = `Bearer ${auth.token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  const resp = await fetch(path, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : null,
  })
  if (resp.status === 401) {
    auth.clear()
    if (!location.hash.includes('/login')) location.hash = '#/login'
    throw new Error('登录已过期，请重新登录')
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(data.detail || `请求失败（${resp.status}）`)
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),
  upload: (p, formData) => request('POST', p, formData, true),
}

/** POST SSE 流式问答（fetch + ReadableStream，EventSource 不支持 POST） */
export async function chatStream(body, { onSources, onDelta, onDone, onRecord, onError }) {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${auth.token}`,
    },
    body: JSON.stringify({ ...body, stream: true }),
  })
  if (!resp.ok || !resp.body) {
    const data = await resp.json().catch(() => ({}))
    throw new Error(data.detail || '连接失败')
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n\n')
    buf = lines.pop() || ''
    for (const line of lines) {
      const payload = line.replace(/^data:\s*/, '').trim()
      if (!payload || payload === '[DONE]') continue
      let event
      try { event = JSON.parse(payload) } catch { continue }
      if (event.type === 'sources') onSources?.(event.sources || [])
      else if (event.type === 'delta') onDelta?.(event.delta || '')
      else if (event.type === 'done') onDone?.(event)
      else if (event.type === 'record') onRecord?.(event.record_id)
      else if (event.type === 'error') onError?.(event.message)
    }
  }
}
