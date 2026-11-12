<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view v-if="route.path === '/login'" />
        <div v-else class="app">
          <header class="app-header">
            <div class="header-inner">
              <div class="brand" @click="router.push('/cases')">
                <span class="seal">研</span>
                <div class="brand-text">
                  <span class="brand-cn">高校思政课程案例研习系统</span>
                </div>
              </div>
              <nav class="nav">
                <a v-for="item in menuItems" :key="item.key" class="nav-link"
                   :class="{ active: isActive(item.key) }" @click="router.push(item.key)">
                  {{ item.label }}
                </a>
              </nav>
              <div class="user-box">
                <span class="role-badge" :class="user?.role">{{ roleLabel }}</span>
                <n-button quaternary size="small" class="logout-btn" @click="logout">退出</n-button>
              </div>
            </div>
          </header>
          <main class="app-main">
            <router-view />
          </main>
          <footer class="app-footer">
            基于检索增强生成（RAG）建设 · 答疑内容句句可溯源 · 教师纠错全程留痕
          </footer>
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth } from './api.js'

const route = useRoute()
const router = useRouter()

const user = computed(() => auth.user)

const roleLabel = computed(() => ({
  student: '学生', teacher: '教师', admin: '管理员',
}[user.value?.role] || '未知'))

const menuItems = computed(() => {
  const items = [
    { label: '案例库', key: '/cases' },
    { label: '研习问答', key: '/ask' },
    { label: '语义检索', key: '/search' },
    { label: '研习记录', key: '/my' },
  ]
  if (['teacher', 'admin'].includes(user.value?.role)) {
    items.push({ label: '案例管理', key: '/manage' })
    items.push({ label: '审核工作台', key: '/review' })
  }
  if (user.value?.role === 'admin') items.push({ label: '用户管理', key: '/users' })
  return items
})

function isActive(key) {
  if (key === '/cases') return route.path.startsWith('/cases')
  return route.path === key
}

function logout() {
  auth.clear()
  router.push('/login')
}

const themeOverrides = {
  common: {
    primaryColor: '#A8342A',
    primaryColorHover: '#BF4638',
    primaryColorPressed: '#8C2A21',
    primaryColorSuppl: '#BF4638',
    infoColor: '#2F4A63',
    infoColorHover: '#3E607E',
    infoColorPressed: '#263F54',
    infoColorSuppl: '#3E607E',
    borderRadius: '3px',
    fontFamily: '"Microsoft YaHei", "PingFang SC", system-ui, sans-serif',
    cardColor: '#FCFAF4',
    textColorBase: '#211C15',
  },
}
</script>

<style>
:root {
  --cinnabar: #A8342A;
  --cinnabar-bright: #C13A2E;
  --cinnabar-wash: #F7E7E0;
  --ink: #211C15;
  --ink-2: #4A4437;
  --ink-3: #8A8172;
  --paper: #F5F0E6;
  --paper-card: #FCFAF4;
  --indigo: #2F4A63;
  --hairline: rgba(33, 28, 21, 0.12);
  --font-display: "Noto Serif SC", "Source Han Serif SC", "SimSun", "STSong", serif;
  --font-kai: "KaiTi", "STKaiti", "DFKai-SB", serif;
  --font-body: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
}

body {
  margin: 0;
  font-family: var(--font-body);
  color: var(--ink);
  background-color: var(--paper);
  background-image:
    radial-gradient(1100px 520px at 88% -8%, rgba(168, 52, 42, 0.06), transparent 62%),
    radial-gradient(900px 480px at -8% 108%, rgba(47, 74, 99, 0.055), transparent 62%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.045'/%3E%3C/svg%3E");
  background-attachment: fixed;
}

.app { min-height: 100vh; display: flex; flex-direction: column; }

/* ── 顶栏：墨色 + 朱砂印章 ── */
.app-header {
  position: sticky; top: 0; z-index: 100;
  background: linear-gradient(180deg, #25201A 0%, #1C1814 100%);
  box-shadow: 0 2px 0 rgba(168, 52, 42, 0.85), 0 6px 20px rgba(20, 15, 10, 0.28);
}
.header-inner {
  max-width: 1200px; margin: 0 auto; padding: 0 24px;
  height: 62px; display: flex; align-items: center; gap: 28px;
}
.brand { display: flex; align-items: center; gap: 12px; cursor: pointer; white-space: nowrap; }
.seal {
  width: 38px; height: 38px; border-radius: 5px; flex: none;
  background: linear-gradient(160deg, #C13A2E, #9E2F25);
  color: #F6F1E6; font-family: var(--font-kai); font-size: 24px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 0 2px rgba(246, 241, 230, 0.35), 0 2px 8px rgba(0, 0, 0, 0.35);
  transform: rotate(-2deg);
  transition: transform 0.25s ease;
}
.brand:hover .seal { transform: rotate(0deg) scale(1.04); }
.brand-text { display: flex; flex-direction: column; justify-content: center; line-height: 1.25; }
.brand-cn {
  font-family: var(--font-display); font-size: 17px; font-weight: 700;
  color: #F3EEDF; letter-spacing: 0.06em;
}

.nav { display: flex; gap: 4px; height: 100%; margin-left: 6px; overflow-x: auto; scrollbar-width: none; }
.nav::-webkit-scrollbar { display: none; }
.nav-link {
  position: relative; display: flex; align-items: center; padding: 0 14px;
  font-size: 14px; color: rgba(238, 231, 214, 0.72); cursor: pointer;
  letter-spacing: 0.04em; transition: color 0.18s ease; user-select: none;
}
.nav-link:hover { color: #F3EEDF; }
.nav-link.active { color: #F6F1E6; }
.nav-link.active::after {
  content: ''; position: absolute; left: 12px; right: 12px; bottom: 0;
  height: 3px; background: var(--cinnabar-bright); border-radius: 2px 2px 0 0;
}

.user-box { margin-left: auto; display: flex; align-items: center; gap: 10px; white-space: nowrap; }
.role-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 3px; letter-spacing: 0.12em;
  border: 1px solid rgba(193, 58, 46, 0.75); color: #E8A79C;
}
.role-badge.admin { border-color: rgba(184, 134, 11, 0.8); color: #E4C87E; }
.role-badge.student { border-color: rgba(122, 137, 160, 0.8); color: #AEBDD2; }
.logout-btn { color: #9A8F7B; }
.logout-btn:hover { color: #F3EEDF !important; }

/* ── 主体 ── */
.app-main { flex: 1; width: 100%; max-width: 1200px; margin: 0 auto; padding: 26px 24px 48px; box-sizing: border-box; }

.app-footer {
  text-align: center; padding: 18px 0 26px;
  font-family: var(--font-kai); font-size: 12px; color: var(--ink-3); letter-spacing: 0.14em;
}
.app-footer::before {
  content: '◆'; color: rgba(168, 52, 42, 0.45); margin-right: 10px; font-size: 9px; vertical-align: 2px;
}
.app-footer::after {
  content: '◆'; color: rgba(168, 52, 42, 0.45); margin-left: 10px; font-size: 9px; vertical-align: 2px;
}

/* ── Naive UI 细节：卡片标题宋体化、卡片纸色描边 ── */
.n-card > .n-card-header .n-card-header__main {
  font-family: var(--font-display); font-weight: 700; letter-spacing: 0.03em;
}
.n-card { box-shadow: 0 1px 3px rgba(33, 28, 21, 0.05); }
</style>
