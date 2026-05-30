<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const email = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')
const route = useRoute()
const router = useRouter()

const requestMagicLink = async () => {
  loading.value = true; error.value = ''; message.value = ''
  try {
    await axios.post('/auth/magic-link', { email: email.value })
    message.value = 'Magic Link gesendet! Bitte prüfe dein Postfach.'
  } catch {
    error.value = 'Fehler beim Senden. Bitte versuche es erneut.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const token = route.query.token as string
  if (!token) return
  loading.value = true
  try {
    const res = await axios.get('/auth/verify', { params: { token } })
    localStorage.setItem('token', res.data.access_token)
    router.push('/')
  } catch {
    error.value = 'Ungültiger oder abgelaufener Link.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div style="min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; position:relative; overflow:hidden; background:var(--bg-base);">
    <div style="position:absolute; width:600px; height:600px; border-radius:50%; background:#06b6d4; opacity:0.05; filter:blur(100px); pointer-events:none;" />
    <div style="position:relative; width:100%; max-width:380px; background:var(--bg-surface); backdrop-filter:blur(20px); border-radius:24px; padding:40px; border:1px solid var(--border); box-shadow:0 0 60px rgba(6,182,212,0.1);">
      <div style="text-align:center; margin-bottom:32px;">
        <div style="font-size:44px; margin-bottom:12px;">🗓️</div>
        <h1 style="font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px;">EventFinder</h1>
        <p style="color:var(--text-secondary); font-size:14px;">Plane gemeinsame Events mit deinen Freunden</p>
      </div>

      <div v-if="loading && !error && !message" style="text-align:center; color:var(--text-secondary); padding:20px 0;">
        Einen Moment...
      </div>

      <form v-else @submit.prevent="requestMagicLink">
        <label style="font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px;">E-Mail Adresse</label>
        <input v-model="email" type="email" placeholder="du@beispiel.de" required
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:12px; padding:13px 16px; color:#fff; font-size:14px; outline:none; margin-bottom:14px; transition:border-color .2s; box-sizing:border-box;"
          @focus="e => (e.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.25)'"
          @blur="e => (e.target as HTMLInputElement).style.borderColor = 'var(--border)'" />

        <button type="submit" :disabled="loading"
          :style="{
            width: '100%',
            padding: '13px',
            borderRadius: '12px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '14px',
            color: '#000',
            background: '#06b6d4',
            boxShadow: '0 0 30px rgba(6,182,212,0.4)',
            transition: 'opacity .2s',
            opacity: loading ? 0.7 : 1,
          }">
          {{ loading ? 'Sende...' : 'Magic Link anfordern ✉️' }}
        </button>

        <p v-if="message" style="color:#10b981; font-size:13px; text-align:center; margin-top:16px;">{{ message }}</p>
        <p v-if="error" style="color:#f43f5e; font-size:13px; text-align:center; margin-top:16px;">{{ error }}</p>
      </form>

      <p style="text-align:center; color:var(--text-muted); font-size:12px; margin-top:24px;">Kein Passwort nötig — du bekommst einen sicheren Link per E-Mail.</p>
    </div>
  </div>
</template>
