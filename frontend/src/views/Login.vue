<template>
  <div class="login-page">
    <div class="login-card">
      <div class="title">
        <el-icon :size="26"><TrendCharts /></el-icon>
        商品历史价格追踪系统
      </div>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="doLogin">
            <el-form-item>
              <el-input v-model="loginForm.username" placeholder="用户名或邮箱" size="large">
                <template #prefix><el-icon><User /></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="doLogin">
                <template #prefix><el-icon><Lock /></el-icon></template>
              </el-input>
            </el-form-item>
            <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" @submit.prevent="doRegister">
            <el-form-item>
              <el-input v-model="regForm.username" placeholder="用户名（3~20 位字母数字下划线）" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.email" placeholder="邮箱" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.nickname" placeholder="昵称（选填）" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.password" type="password" placeholder="密码（>=8 位，含字母和数字）" size="large" show-password />
            </el-form-item>
            <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doRegister">注 册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <div class="muted" style="margin-top: 12px">管理员账号：admin / admin123456</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '../api'
import { useAuthStore } from '../store'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '', remember: true })
const regForm = reactive({ username: '', password: '', email: '', nickname: '' })

async function doLogin() {
  loading.value = true
  try {
    const { data } = await api.post('/api/auth/login', loginForm)
    auth.login(data.token, data.user)
    ElMessage.success('登录成功')
    router.push(data.role === 'admin' ? '/admin' : '/')
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  loading.value = true
  try {
    await api.post('/api/auth/register', regForm)
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    loginForm.username = regForm.username
    loginForm.password = regForm.password
  } catch (e) {
    ElMessage.error(errMsg(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #409eff 0%, #53a8ff 50%, #79bbff 100%);
}
.login-card { width: 400px; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 12px 40px rgba(0,0,0,.15); }
.title { display: flex; align-items: center; gap: 8px; font-size: 20px; font-weight: 700; justify-content: center; margin-bottom: 18px; color: #303133; }
</style>
