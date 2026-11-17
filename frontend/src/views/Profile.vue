<template>
  <div class="page">
    <div class="card" style="max-width: 560px">
      <h3 class="page-title">个人中心</h3>
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input :model-value="auth.user?.username" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.password" type="password" show-password placeholder="不修改请留空（>=8 位含字母数字）" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="save">保存修改</el-button>
        </el-form-item>
      </el-form>
      <div class="muted">角色：{{ auth.isAdmin ? '管理员' : '普通用户' }} · 注册时间：{{ auth.user ? '—' : '—' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'

const auth = useAuthStore()
const loading = ref(false)
const form = reactive({
  nickname: auth.user?.nickname || '',
  email: auth.user?.email || '',
  password: '',
})

async function save() {
  loading.value = true
  try {
    const payload: any = { nickname: form.nickname, email: form.email }
    if (form.password) payload.password = form.password
    await api.put('/api/auth/profile', payload)
    if (auth.user) {
      auth.user.nickname = form.nickname
      auth.user.email = form.email
      localStorage.setItem('spt_user', JSON.stringify(auth.user))
    }
    ElMessage.success('修改成功')
    form.password = ''
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}
</script>
