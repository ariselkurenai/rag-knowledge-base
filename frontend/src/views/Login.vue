<template>
  <div class="login-page">
    <div class="login-wrap">
      <div class="login-head">
        <span class="login-seal">研<br />習</span>
        <div class="login-title">高校思政课程案例研习系统</div>
        <div class="login-sub">案例可溯源 · 答疑有出处 · 纠错全留痕</div>
      </div>
      <n-card class="login-card" :bordered="false">
        <n-tabs v-model:value="tab" size="large" justify-content="center">
          <n-tab-pane name="login" tab="登录">
            <n-form :model="loginForm" label-placement="left" label-width="60">
              <n-form-item label="用户名">
                <n-input v-model:value="loginForm.username" placeholder="用户名" @keyup.enter="doLogin" />
              </n-form-item>
              <n-form-item label="密码">
                <n-input v-model:value="loginForm.password" type="password" show-password-on="click"
                         placeholder="密码" @keyup.enter="doLogin" />
              </n-form-item>
              <n-button type="primary" block :loading="loading" @click="doLogin">登 录</n-button>
            </n-form>
          </n-tab-pane>
          <n-tab-pane name="register" tab="学生注册">
            <n-form :model="regForm" label-placement="left" label-width="60">
              <n-form-item label="用户名">
                <n-input v-model:value="regForm.username" placeholder="2-50 个字符" />
              </n-form-item>
              <n-form-item label="密码">
                <n-input v-model:value="regForm.password" type="password" show-password-on="click"
                         placeholder="至少 6 位" />
              </n-form-item>
              <n-form-item label="确认">
                <n-input v-model:value="regForm.confirm" type="password" show-password-on="click"
                         placeholder="再次输入密码" @keyup.enter="doRegister" />
              </n-form-item>
              <n-button type="primary" block :loading="loading" @click="doRegister">注 册</n-button>
            </n-form>
          </n-tab-pane>
        </n-tabs>
        <n-alert type="info" :bordered="false" style="margin-top: 12px">
          演示账号：teacher / 123456（教师）　admin / 123456（管理员）
        </n-alert>
      </n-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api, auth } from '../api.js'

const router = useRouter()
const message = useMessage()
const tab = ref('login')
const loading = ref(false)
const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', confirm: '' })

async function doLogin() {
  if (!loginForm.username || !loginForm.password) return message.warning('请输入用户名和密码')
  loading.value = true
  try {
    const data = await api.post('/api/auth/login', loginForm)
    auth.save(data.token, data.user)
    message.success(`欢迎回来，${data.user.username}`)
    router.push('/cases')
  } catch (e) { message.error(e.message) } finally { loading.value = false }
}

async function doRegister() {
  if (!regForm.username || regForm.password.length < 6) return message.warning('请检查用户名和密码（至少 6 位）')
  if (regForm.password !== regForm.confirm) return message.warning('两次密码不一致')
  loading.value = true
  try {
    await api.post('/api/auth/register', { username: regForm.username, password: regForm.password })
    message.success('注册成功，请登录')
    loginForm.username = regForm.username
    loginForm.password = ''
    tab.value = 'login'
  } catch (e) { message.error(e.message) } finally { loading.value = false }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 40px 20px;
  box-sizing: border-box;
}
.login-wrap { width: 420px; animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes rise {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}
.login-head { text-align: center; margin-bottom: 26px; }
.login-seal {
  display: inline-flex; align-items: center; justify-content: center;
  width: 64px; height: 64px; border-radius: 8px; margin-bottom: 18px;
  background: linear-gradient(160deg, #C13A2E, #9E2F25);
  color: #F6F1E6; font-family: var(--font-kai); font-size: 22px; font-weight: 700;
  line-height: 1.15; text-align: center;
  box-shadow: inset 0 0 0 2px rgba(246, 241, 230, 0.35), 0 8px 24px rgba(158, 47, 37, 0.35);
  transform: rotate(-2deg);
}
.login-title {
  font-family: var(--font-display); font-size: 26px; font-weight: 700;
  color: var(--ink); letter-spacing: 0.14em;
}
.login-sub {
  font-family: var(--font-kai); font-size: 13px; color: var(--ink-3);
  margin-top: 8px; letter-spacing: 0.22em;
}
.login-card {
  border-radius: 6px; border: 1px solid var(--hairline);
  box-shadow: 0 18px 44px rgba(33, 28, 21, 0.14), 0 2px 6px rgba(33, 28, 21, 0.06);
}
</style>
