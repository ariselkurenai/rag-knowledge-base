<template>
  <n-config-provider :theme-overrides="theme">
    <n-message-provider>
      <n-dialog-provider>
        <div class="app">
          <n-layout v-if="$route.path !== '/login'" position="absolute">
            <n-layout-header bordered class="header">
              <div class="header-inner">
                <div class="brand" @click="$router.push('/cases')">
                  🎓 高校思政课程案例研习系统
                </div>
                <n-menu mode="horizontal" :options="menuOptions" :value="$route.path"
                        @update:value="(k) => $router.push(k)" />
                <div class="user-box">
                  <n-tag :type="roleType" size="small">{{ roleLabel }}</n-tag>
                  <span class="username">{{ user?.username }}</span>
                  <n-button quaternary size="small" @click="logout">退出</n-button>
                </div>
              </div>
            </n-layout-header>
            <n-layout-content content-style="padding: 20px; max-width: 1200px; margin: 0 auto;">
              <router-view />
            </n-layout-content>
          </n-layout>
          <router-view v-else />
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { computed, h } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { auth } from './api.js'

const router = useRouter()
const user = computed(() => auth.user)

const roleLabel = computed(() => ({
  student: '学生', teacher: '教师', admin: '管理员',
}[user.value?.role] || '未知'))
const roleType = computed(() => ({
  student: 'info', teacher: 'success', admin: 'warning',
}[user.value?.role] || 'default'))

const menuOptions = computed(() => {
  const items = [
    { label: '案例库', key: '/cases' },
    { label: '研习问答', key: '/ask' },
    { label: '语义检索', key: '/search' },
    { label: '我的记录', key: '/my' },
  ]
  if (['teacher', 'admin'].includes(user.value?.role)) {
    items.push({ label: '案例管理', key: '/manage' })
    items.push({ label: '审核工作台', key: '/review' })
  }
  if (user.value?.role === 'admin') items.push({ label: '用户管理', key: '/users' })
  return items
})

function logout() {
  auth.clear()
  router.push('/login')
}

const theme = {
  common: { primaryColor: '#1f4e79', primaryColorHover: '#2b6cb0' },
}
</script>

<style>
body { margin: 0; font-family: 'Microsoft YaHei', system-ui, sans-serif; }
.header { padding: 0 24px; height: 56px; display: flex; align-items: center; }
.header-inner { display: flex; align-items: center; gap: 20px; width: 100%; }
.brand { font-size: 17px; font-weight: bold; color: #1f4e79; cursor: pointer; white-space: nowrap; }
.user-box { margin-left: auto; display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.username { font-size: 13px; color: #4a5568; }
</style>
