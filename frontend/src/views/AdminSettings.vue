<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const { headers } = useAuth()

const form = ref<Record<string, string>>({
  mail_server: '',
  mail_port: '587',
  mail_username: '',
  mail_password: '',
  mail_from: '',
  frontend_url: '',
})
const passwordSet = ref(false)
const saving = ref(false)
const testing = ref(false)
const saveMsg = ref('')
const testResult = ref<{ success: boolean; error?: string } | null>(null)

async function load() {
  try {
    const res = await axios.get('/api/admin/settings', { headers: headers() })
    const d = res.data
    form.value.mail_server = d.mail_server ?? ''
    form.value.mail_port = d.mail_port ?? '587'
    form.value.mail_username = d.mail_username ?? ''
    form.value.mail_from = d.mail_from ?? ''
    form.value.frontend_url = d.frontend_url ?? ''
    passwordSet.value = d.mail_password === '***'
    form.value.mail_password = ''
  } catch (e: any) {
    if (e.response?.status === 403) window.location.href = '/'
  }
}

async function save() {
  saving.value = true; saveMsg.value = ''
  try {
    const payload: Record<string, string> = {
      mail_server: form.value.mail_server,
      mail_port: form.value.mail_port,
      mail_username: form.value.mail_username,
      mail_from: form.value.mail_from,
      frontend_url: form.value.frontend_url,
    }
    if (form.value.mail_password) payload.mail_password = form.value.mail_password
    await axios.put('/api/admin/settings', payload, { headers: headers() })
    saveMsg.value = 'Gespeichert ✓'
    passwordSet.value = true
    form.value.mail_password = ''
  } catch (e: any) {
    saveMsg.value = e.response?.data?.detail ?? 'Fehler beim Speichern'
  } finally {
    saving.value = false
  }
}

async function testMail() {
  testing.value = true; testResult.value = null
  try {
    const res = await axios.post('/api/admin/settings/test-mail', {}, { headers: headers() })
    testResult.value = res.data
  } catch (e: any) {
    testResult.value = { success: false, error: e.response?.data?.detail ?? 'Netzwerkfehler' }
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <div style="padding:16px 32px; border-bottom:1px solid var(--border); background:rgba(8,11,20,0.8); backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:12px;">
      <router-link to="/" style="color:var(--text-secondary); text-decoration:none; font-size:14px;">← Dashboard</router-link>
      <span style="color:var(--border);">|</span>
      <span style="font-weight:600; font-size:14px;">⚙️ Einstellungen</span>
    </div>

    <main style="max-width:600px; margin:0 auto; padding:40px 24px;">
      <h1 style="font-size:24px; font-weight:700; margin-bottom:8px;">App-Einstellungen</h1>
      <p style="color:var(--text-secondary); font-size:14px; margin-bottom:32px;">
        Konfiguration wird verschlüsselt in der Datenbank gespeichert.
      </p>

      <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:28px; display:flex; flex-direction:column; gap:18px;">
        <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em;">E-Mail / SMTP</p>

        <div v-for="field in [
          { key: 'mail_server',   label: 'SMTP-Server',    placeholder: 'smtp.web.de',                         type: 'text'   },
          { key: 'mail_port',     label: 'SMTP-Port',      placeholder: '587',                                  type: 'number' },
          { key: 'mail_username', label: 'Benutzername',   placeholder: 'du@web.de',                            type: 'email'  },
          { key: 'mail_from',     label: 'Absender',       placeholder: 'du@web.de',                            type: 'email'  },
          { key: 'frontend_url',  label: 'Frontend-URL',   placeholder: 'https://eventfinder.thunderbee.uk',    type: 'text'   },
        ]" :key="field.key">
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">{{ field.label }}</label>
          <input v-model="form[field.key]" :type="field.type" :placeholder="field.placeholder"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
        </div>

        <!-- Passwort -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Passwort</label>
          <input v-model="form.mail_password" type="password"
            :placeholder="passwordSet ? '●●●●●●●● (unverändert lassen)' : 'Passwort eingeben'"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
          <p style="font-size:11px; color:rgba(255,255,255,0.3); margin-top:5px;">
            Leer lassen um das bestehende Passwort nicht zu ändern
          </p>
        </div>

        <p v-if="saveMsg" :style="{ fontSize:'13px', color: saveMsg.includes('✓') ? '#10b981' : '#f43f5e' }">
          {{ saveMsg }}
        </p>

        <div style="display:flex; gap:10px; margin-top:8px;">
          <button @click="save" :disabled="saving"
            :style="{
              flex:1, padding:'11px', borderRadius:'10px', border:'none', cursor:'pointer',
              fontWeight:600, fontSize:'14px', color:'#000', background:'#06b6d4',
              boxShadow:'0 0 20px rgba(6,182,212,0.3)', opacity: saving ? 0.7 : 1,
            }">
            {{ saving ? 'Speichern...' : 'Speichern' }}
          </button>
          <button @click="testMail" :disabled="testing"
            :style="{
              flex:1, padding:'11px', borderRadius:'10px',
              background:'transparent', border:'1px solid rgba(255,255,255,0.15)',
              color:'rgba(255,255,255,0.7)', cursor:'pointer', fontSize:'14px',
              opacity: testing ? 0.7 : 1,
            }">
            {{ testing ? 'Sende...' : 'Test-E-Mail senden' }}
          </button>
        </div>

        <div v-if="testResult" :style="{
          padding:'12px 16px', borderRadius:'10px', fontSize:'13px',
          background: testResult.success ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
          border: `1px solid ${testResult.success ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
          color: testResult.success ? '#10b981' : '#f43f5e',
        }">
          {{ testResult.success ? '✓ Test-E-Mail erfolgreich gesendet!' : `✗ Fehler: ${testResult.error}` }}
        </div>
      </div>
    </main>
  </div>
</template>
