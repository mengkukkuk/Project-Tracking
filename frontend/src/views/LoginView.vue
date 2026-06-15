<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const mode = ref('login') // 'login' | 'register'
const form = ref({ name: '', email: '', password: '' })
const loading = ref(false)
const isDev = import.meta.env.DEV

async function submit() {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.value.email, form.value.password)
    } else {
      await auth.register(form.value)
    }
    ui.success('เข้าสู่ระบบสำเร็จ')
    router.push(route.query.redirect || '/')
  } catch (e) {
    ui.error(e.message)
  } finally {
    loading.value = false
  }
}

function fillDemo() {
  if (!isDev) return
  mode.value = 'login'
  form.value = { name: '', email: 'admin@scada.local', password: 'admin123' }
}
</script>

<template>
  <div class="auth">
    <div class="panel card">
      <div class="logo mono">PTK</div>
      <h1>Project-Tracking</h1>
      <p class="sub">{{ mode === 'login' ? 'เข้าสู่ระบบเพื่อดำเนินการต่อ' : 'สร้างบัญชีใหม่' }}</p>

      <form @submit.prevent="submit">
        <label v-if="mode === 'register'" class="field">
          <span>ชื่อ</span>
          <input v-model="form.name" class="input" required />
        </label>
        <label class="field">
          <span>อีเมล</span>
          <input v-model="form.email" type="email" class="input" required autocomplete="username" />
        </label>
        <label class="field">
          <span>รหัสผ่าน</span>
          <input v-model="form.password" type="password" class="input" required autocomplete="current-password" />
        </label>
        <button class="btn" style="width:100%;margin-top:6px" :disabled="loading">
          {{ loading ? 'กำลังดำเนินการ...' : (mode === 'login' ? 'เข้าสู่ระบบ' : 'สมัครสมาชิก') }}
        </button>
      </form>

      <div class="switch">
        <template v-if="mode === 'login'">
          ยังไม่มีบัญชี?
          <a @click="mode = 'register'">สมัครสมาชิก</a>
        </template>
        <template v-else>
          มีบัญชีอยู่แล้ว?
          <a @click="mode = 'login'">เข้าสู่ระบบ</a>
        </template>
      </div>

      <button v-if="isDev" class="demo" @click="fillDemo">ใช้บัญชีเดโม (admin@scada.local)</button>
    </div>
  </div>
</template>

<style scoped>
.auth { min-height: 100vh; display: grid; place-items: center; padding: 20px;
  background: radial-gradient(1200px 600px at 70% -10%, rgba(20,184,166,.18), transparent), var(--bg); }
.panel { width: 100%; max-width: 380px; padding: 32px 28px; text-align: center; }
.logo { width: 48px; height: 48px; border-radius: 12px; background: var(--accent); color: #fff;
  font-weight: 700; font-size: 16px; display: grid; place-items: center; margin: 0 auto 16px; }
h1 { font-size: 19px; font-weight: 700; color: var(--text); }
.sub { font-size: 13px; color: var(--text-dim); margin: 6px 0 22px; }
form { display: flex; flex-direction: column; gap: 14px; text-align: left; }
.switch { margin-top: 18px; font-size: 13px; color: var(--text-dim); }
.switch a { color: var(--accent); cursor: pointer; font-weight: 600; }
.switch a:hover { text-decoration: underline; }
.demo { margin-top: 14px; background: none; border: none; color: var(--text-dim); font-size: 12px;
  cursor: pointer; text-decoration: underline; font-family: inherit; }
.demo:hover { color: var(--accent); }
</style>
