<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const email = ref('')
const loading = ref(false)
const confirming = ref(false)
const message = ref('')
const error = ref('')
const route = useRoute()
const router = useRouter()

const pendingToken = computed(() => route.query.token as string | undefined)
const pendingEvent = computed(() => route.query.event as string | undefined)

const requestMagicLink = async () => {
  loading.value = true; error.value = ''; message.value = ''
  try {
    await axios.post('/auth/magic-link', { email: email.value })
    message.value = 'Anmelde-Link gesendet! Bitte prüfe dein Postfach.'
  } catch {
    error.value = 'Fehler beim Senden. Bitte versuche es erneut.'
  } finally {
    loading.value = false
  }
}

const confirmLogin = async () => {
  if (!pendingToken.value) return
  confirming.value = true; error.value = ''
  try {
    const res = await axios.get('/auth/verify', { params: { token: pendingToken.value } })
    localStorage.setItem('token', res.data.access_token)
    router.replace(pendingEvent.value ? `/event/${pendingEvent.value}` : '/')
  } catch {
    error.value = 'Dieser Link ist ungültig oder bereits abgelaufen. Bitte fordere einen neuen an.'
    confirming.value = false
  }
}

onMounted(() => {
  // Kein automatisches Konsumieren — der Nutzer muss den Button klicken
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

      <!-- Bestätigungs-Screen wenn Token in URL vorhanden -->
      <div v-if="pendingToken && !error">
        <p style="color:var(--text-secondary); font-size:14px; text-align:center; margin-bottom:24px; line-height:1.6;">
          Du wurdest eingeladen{{ pendingEvent ? ' zu einem Event' : '' }}.<br>
          Klicke auf den Button um dich anzumelden.
        </p>
        <button @click="confirmLogin" :disabled="confirming"
          :style="{
            width: '100%', padding: '13px', borderRadius: '12px', border: 'none',
            cursor: confirming ? 'default' : 'pointer', fontWeight: 600, fontSize: '14px',
            color: '#000', background: '#06b6d4', boxShadow: '0 0 30px rgba(6,182,212,0.4)',
            transition: 'opacity .2s', opacity: confirming ? 0.7 : 1,
          }">
          {{ confirming ? 'Anmeldung läuft…' : 'Jetzt anmelden →' }}
        </button>
      </div>

      <!-- Fehler nach Token-Verarbeitung -->
      <div v-else-if="pendingToken && error">
        <p style="color:#f43f5e; font-size:13px; text-align:center; margin-bottom:20px; line-height:1.6;">{{ error }}</p>
        <form @submit.prevent="requestMagicLink">
          <label style="font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px;">E-Mail Adresse</label>
          <input v-model="email" type="email" placeholder="du@beispiel.de" required
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:12px; padding:13px 16px; color:#fff; font-size:14px; outline:none; margin-bottom:14px; transition:border-color .2s; box-sizing:border-box;"
            @focus="e => (e.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.25)'"
            @blur="e => (e.target as HTMLInputElement).style.borderColor = 'var(--border)'" />
          <button type="submit" :disabled="loading"
            :style="{ width:'100%', padding:'13px', borderRadius:'12px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background:'#06b6d4', opacity: loading ? 0.7 : 1 }">
            {{ loading ? 'Sende...' : 'Neuen Link anfordern ✉️' }}
          </button>
          <p v-if="message" style="color:#10b981; font-size:13px; text-align:center; margin-top:16px;">{{ message }}</p>
        </form>
      </div>

      <!-- Standard Login-Formular -->
      <form v-else @submit.prevent="requestMagicLink">
        <label style="font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px;">E-Mail Adresse</label>
        <input v-model="email" type="email" placeholder="du@beispiel.de" required
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:12px; padding:13px 16px; color:#fff; font-size:14px; outline:none; margin-bottom:14px; transition:border-color .2s; box-sizing:border-box;"
          @focus="e => (e.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.25)'"
          @blur="e => (e.target as HTMLInputElement).style.borderColor = 'var(--border)'" />

        <button type="submit" :disabled="loading"
          :style="{
            width: '100%', padding: '13px', borderRadius: '12px', border: 'none',
            cursor: 'pointer', fontWeight: 600, fontSize: '14px', color: '#000',
            background: '#06b6d4', boxShadow: '0 0 30px rgba(6,182,212,0.4)',
            transition: 'opacity .2s', opacity: loading ? 0.7 : 1,
          }">
          {{ loading ? 'Sende...' : 'Anmelde-Link anfordern ✉️' }}
        </button>

        <p v-if="message" style="color:#10b981; font-size:13px; text-align:center; margin-top:16px;">{{ message }}</p>
        <p v-if="error" style="color:#f43f5e; font-size:13px; text-align:center; margin-top:16px;">{{ error }}</p>
      </form>

      <p style="text-align:center; color:var(--text-muted); font-size:12px; margin-top:24px;">Kein Passwort nötig — du bekommst einen sicheren Link per E-Mail.</p>
    </div>
  </div>
</template>
