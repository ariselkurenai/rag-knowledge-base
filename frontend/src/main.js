import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import naive from 'naive-ui'
import App from './App.vue'
import { auth } from './api.js'
import Login from './views/Login.vue'
import Cases from './views/Cases.vue'
import CaseRead from './views/CaseRead.vue'
import Search from './views/Search.vue'
import Ask from './views/Ask.vue'
import MyRecords from './views/MyRecords.vue'
import Manage from './views/Manage.vue'
import Review from './views/Review.vue'
import AdminUsers from './views/AdminUsers.vue'

const routes = [
  { path: '/login', component: Login },
  { path: '/', redirect: '/cases' },
  { path: '/cases', component: Cases, meta: { title: '案例库' } },
  { path: '/cases/:docId', component: CaseRead, meta: { title: '案例阅读' } },
  { path: '/search', component: Search, meta: { title: '语义检索' } },
  { path: '/ask', component: Ask, meta: { title: '研习问答' } },
  { path: '/my', component: MyRecords, meta: { title: '研习记录' } },
  { path: '/manage', component: Manage, meta: { title: '案例管理', roles: ['teacher', 'admin'] } },
  { path: '/review', component: Review, meta: { title: '审核工作台', roles: ['teacher', 'admin'] } },
  { path: '/users', component: AdminUsers, meta: { title: '用户管理', roles: ['admin'] } },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  if (to.path === '/login') return true
  if (!auth.token) return '/login'
  const roles = to.meta.roles
  if (roles && !roles.includes(auth.user?.role)) return '/cases'
  return true
})

createApp(App).use(router).use(naive).mount('#app')
