<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const props = defineProps<{ eventId: string; accentColor: string }>()
const emit = defineEmits<{ close: []; invited: [] }>()
const { headers } = useAuth()

const email = ref('')
const message = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

async function invite() {
  error.value = ''; success.value = ''
  if (!email.value.trim()) { error.value = 'E-Mail erforderlich'; return }
  loading.value = true
  try {
    await axios.post(
      `/events/${props.eventId}/invite`,
      { email: email.value, message: message.value || null },
      { headers: headers() }
    )
    success.value = `${email.value} wurde eingeladen!`
    email.value = ''
    message.value = ''
    emit('invited')
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Fehler beim Einladen'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);" @click.self="emit('close')">
    <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:400px;">
      <h2 style="font-size:18px; font-weight:700; margin-bottom:20px;">Teilnehmer einladen</h2>
      <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">E-Mail-Adresse</label>
      <input v-model="email" type="email" placeholder="freund@beispiel.de" @keyup.enter="invite" style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:14px; box-sizing:border-box;" />
      <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Persönliche Nachricht <span style="color:rgba(255,255,255,0.25);">(optional)</span></label>
      <textarea v-model="message" placeholder="Freue mich auf dich dabei! …" rows="3"
        style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:16px; box-sizing:border-box; resize:vertical; font-family:inherit;"></textarea>
      <p v-if="error" style="color:#f43f5e; font-size:13px; margin-bottom:12px;">{{ error }}</p>
      <p v-if="success" style="color:#10b981; font-size:13px; margin-bottom:12px;">{{ success }}</p>
      <div style="display:flex; justify-content:flex-end; gap:10px;">
        <button @click="emit('close')" style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Schließen</button>
        <button @click="invite" :disabled="loading" :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: accentColor, opacity: loading ? 0.7 : 1 }">{{ loading ? '...' : 'Einladen' }}</button>
      </div>
    </div>
  </div>
</template>
