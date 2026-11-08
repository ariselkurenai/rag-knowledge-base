<template>
  <div>
    <n-card title="用户管理" size="small">
      <n-data-table :columns="cols" :data="users" :loading="loading" size="small" />
    </n-card>
  </div>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NSelect, NSpace, NTag, useDialog, useMessage } from 'naive-ui'
import { api } from '../api.js'

const message = useMessage()
const dialog = useDialog()
const users = ref([])
const loading = ref(false)

const roleOptions = [
  { label: '学生', value: 'student' },
  { label: '教师', value: 'teacher' },
  { label: '管理员', value: 'admin' },
]

const cols = [
  { title: 'ID', key: 'id', width: 50 },
  { title: '用户名', key: 'username' },
  {
    title: '角色', width: 160, render: (u) => h(NTag, {
      size: 'small', type: { student: 'info', teacher: 'success', admin: 'warning' }[u.role],
    }, { default: () => ({ student: '学生', teacher: '教师', admin: '管理员' }[u.role] || u.role) }),
  },
  { title: '研习记录数', key: 'record_count', width: 100 },
  { title: '注册时间', render: (u) => u.created_at?.slice(0, 10) },
  {
    title: '角色调整', width: 200, render: (u) => h(NSpace, { size: 'small' }, { default: () => [
      h(NSelect, {
        size: 'tiny', value: u.role, options: roleOptions, style: 'width: 110px',
        onUpdateValue: (v) => confirmChange(u, v),
      }),
      h(NButton, {
        size: 'tiny', type: 'error', ghost: true,
        onClick: () => confirmChange(u, u.role === 'student' ? 'teacher' : 'student'),
      }, { default: () => '快速切换' }),
    ] }),
  },
]

function confirmChange(u, newRole) {
  if (newRole === u.role) return
  dialog.warning({
    title: '调整角色',
    content: `将用户「${u.username}」的角色调整为「${{ student: '学生', teacher: '教师', admin: '管理员' }[newRole]}」？操作将记入审计日志。`,
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.put(`/api/users/${u.id}/role`, { role: newRole })
        message.success('角色已调整（已留痕）')
        load()
      } catch (e) { message.error(e.message) }
    },
  })
}

async function load() {
  loading.value = true
  try { users.value = await api.get('/api/users') }
  catch { users.value = [] } finally { loading.value = false }
}

onMounted(load)
</script>
