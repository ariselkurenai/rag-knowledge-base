<template>
  <div class="login-page">
    <n-card class="login-card" :bordered="false">
      <div class="title">🎓 高校思政课程案例研习系统</div>
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
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1f4e79 0%, #2b6cb0 100%);
}
.login-card { width: 400px; border-radius: 8px; }
.title { text-align: center; font-size: 18px; font-weight: bold; color: #1f4e79; margin-bottom: 16px; }
</style>
