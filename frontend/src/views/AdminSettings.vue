<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const { headers } = useAuth()

const activeTab = ref<'smtp' | 'rotation'>('smtp')

// --- SMTP ---
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

async function loadSmtp() {
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

// --- Rotation ---
interface RotationEntry { user_id: string; name: string; email: string; order_index: number; is_active: boolean; last_organized_at?: string }
interface UserEntry { id: string; name: string; email: string }

const rotation = ref<RotationEntry[]>([])
const allUsers = ref<UserEntry[]>([])
const rotSaving = ref(false)
const rotMsg = ref('')

async function loadRotation() {
  const [rotRes, usersRes] = await Promise.all([
    axios.get('/api/admin/rotation', { headers: headers() }),
    axios.get('/api/admin/users', { headers: headers() }),
  ])
  rotation.value = rotRes.data
  allUsers.value = usersRes.data
}

const usersNotInRotation = () =>
  allUsers.value.filter(u => !rotation.value.some(r => r.user_id === u.id))

function addToRotation(user: UserEntry) {
  rotation.value.push({
    user_id: user.id, name: user.name, email: user.email,
    order_index: rotation.value.length, is_active: true,
  })
}

function removeFromRotation(userId: string) {
  rotation.value = rotation.value.filter(r => r.user_id !== userId)
}

function moveUp(i: number) {
  if (i === 0) return
  const tmp = rotation.value[i - 1]
  rotation.value[i - 1] = rotation.value[i]
  rotation.value[i] = tmp
}

function moveDown(i: number) {
  if (i >= rotation.value.length - 1) return
  const tmp = rotation.value[i + 1]
  rotation.value[i + 1] = rotation.value[i]
  rotation.value[i] = tmp
}

async function saveRotation() {
  rotSaving.value = true; rotMsg.value = ''
  try {
    await axios.put('/api/admin/rotation', rotation.value.map((r, i) => ({
      user_id: r.user_id, is_active: r.is_active, order_index: i,
    })), { headers: headers() })
    rotMsg.value = 'Gespeichert ✓'
    await loadRotation()
  } catch (e: any) {
    rotMsg.value = e.response?.data?.detail ?? 'Fehler beim Speichern'
  } finally {
    rotSaving.value = false
  }
}

onMounted(async () => {
  await loadSmtp()
  await loadRotation()
})
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <div style="padding:16px 32px; border-bottom:1px solid var(--border); background:rgba(8,11,20,0.8); backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:12px;">
      <router-link to="/" style="color:var(--text-secondary); text-decoration:none; font-size:14px;">← Dashboard</router-link>
      <span style="color:var(--border);">|</span>
      <span style="font-weight:600; font-size:14px;">⚙️ Einstellungen</span>
    </div>

    <main style="max-width:640px; margin:0 auto; padding:40px 24px;">
      <h1 style="font-size:24px; font-weight:700; margin-bottom:24px;">App-Einstellungen</h1>

      <!-- Tabs -->
      <div style="display:flex; gap:4px; margin-bottom:28px; background:rgba(255,255,255,0.05); border-radius:12px; padding:4px;">
        <button v-for="tab in [{ id: 'smtp', label: '✉ E-Mail / SMTP' }, { id: 'rotation', label: '🔄 Organisator-Rotation' }]"
          :key="tab.id"
          @click="activeTab = tab.id as any"
          :style="{
            flex:1, padding:'9px', borderRadius:'9px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px',
            background: activeTab === tab.id ? 'rgba(255,255,255,0.1)' : 'transparent',
            color: activeTab === tab.id ? '#fff' : 'rgba(255,255,255,0.45)',
          }">{{ tab.label }}</button>
      </div>

      <!-- SMTP-Tab -->
      <div v-if="activeTab === 'smtp'">
        <p style="color:var(--text-secondary); font-size:14px; margin-bottom:24px;">
          Konfiguration wird verschlüsselt in der Datenbank gespeichert.
        </p>
        <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.12); border-radius:16px; padding:28px; display:flex; flex-direction:column; gap:18px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.55); text-transform:uppercase; letter-spacing:.1em; font-weight:600;">E-Mail / SMTP</p>

          <div v-for="field in [
            { key: 'mail_server',   label: 'SMTP-Server',    placeholder: 'smtp.web.de',                         type: 'text'   },
            { key: 'mail_port',     label: 'SMTP-Port',      placeholder: '587',                                  type: 'number' },
            { key: 'mail_username', label: 'Benutzername',   placeholder: 'du@web.de',                            type: 'email'  },
            { key: 'mail_from',     label: 'Absender',       placeholder: 'du@web.de',                            type: 'email'  },
            { key: 'frontend_url',  label: 'Frontend-URL',   placeholder: 'https://eventfinder.thunderbee.uk',    type: 'text'   },
          ]" :key="field.key">
            <label style="font-size:13px; color:rgba(255,255,255,0.65); display:block; margin-bottom:7px; font-weight:500;">{{ field.label }}</label>
            <input v-model="form[field.key]" :type="field.type" :placeholder="field.placeholder"
              style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.18); border-radius:10px; padding:11px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; color-scheme:dark;" />
          </div>

          <div>
            <label style="font-size:13px; color:rgba(255,255,255,0.65); display:block; margin-bottom:7px; font-weight:500;">Passwort</label>
            <input v-model="form.mail_password" type="password"
              :placeholder="passwordSet ? '●●●●●●●● (unverändert lassen)' : 'Passwort eingeben'"
              style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.18); border-radius:10px; padding:11px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
            <p style="font-size:12px; color:rgba(255,255,255,0.4); margin-top:6px;">Leer lassen um das bestehende Passwort nicht zu ändern</p>
          </div>

          <p v-if="saveMsg" :style="{ fontSize:'13px', color: saveMsg.includes('✓') ? '#10b981' : '#f43f5e' }">{{ saveMsg }}</p>

          <div style="display:flex; gap:10px; margin-top:8px;">
            <button @click="save" :disabled="saving"
              :style="{ flex:1, padding:'11px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background:'#06b6d4', boxShadow:'0 0 20px rgba(6,182,212,0.3)', opacity: saving ? 0.7 : 1 }">
              {{ saving ? 'Speichern...' : 'Speichern' }}
            </button>
            <button @click="testMail" :disabled="testing"
              :style="{ flex:1, padding:'11px', borderRadius:'10px', background:'transparent', border:'1px solid rgba(255,255,255,0.15)', color:'rgba(255,255,255,0.7)', cursor:'pointer', fontSize:'14px', opacity: testing ? 0.7 : 1 }">
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
      </div>

      <!-- Rotations-Tab -->
      <div v-if="activeTab === 'rotation'">
        <p style="color:var(--text-secondary); font-size:14px; margin-bottom:24px;">
          Legt fest, wer beim nächsten Event als Organisator vorgeschlagen wird.
        </p>

        <!-- Aktuelle Reihenfolge -->
        <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.12); border-radius:16px; padding:24px; margin-bottom:16px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px;">Reihenfolge</p>

          <div v-if="rotation.length === 0" style="color:rgba(255,255,255,0.25); font-size:13px; padding:12px 0;">
            Noch keine Personen in der Rotation.
          </div>

          <div v-for="(entry, i) in rotation" :key="entry.user_id"
            style="display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
            <span style="font-size:13px; color:rgba(255,255,255,0.25); width:20px; text-align:center; flex-shrink:0;">{{ i + 1 }}</span>
            <div style="flex:1; min-width:0;">
              <p style="font-size:14px; font-weight:500; margin:0;">{{ entry.name }}</p>
              <p style="font-size:11px; color:rgba(255,255,255,0.3); margin:2px 0 0;">{{ entry.email }}</p>
            </div>
            <!-- Aktiv-Toggle -->
            <button @click="entry.is_active = !entry.is_active"
              :style="{
                padding:'3px 10px', borderRadius:'6px', border:'1px solid', cursor:'pointer', fontSize:'12px', fontWeight:600,
                borderColor: entry.is_active ? 'rgba(16,185,129,0.4)' : 'rgba(255,255,255,0.12)',
                background: entry.is_active ? 'rgba(16,185,129,0.12)' : 'transparent',
                color: entry.is_active ? '#10b981' : 'rgba(255,255,255,0.3)',
              }">{{ entry.is_active ? 'Aktiv' : 'Pausiert' }}</button>
            <!-- Pfeile -->
            <button @click="moveUp(i)" :disabled="i === 0"
              style="background:transparent; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:rgba(255,255,255,0.4); cursor:pointer; padding:3px 8px; font-size:13px;" :style="{ opacity: i === 0 ? 0.3 : 1 }">↑</button>
            <button @click="moveDown(i)" :disabled="i >= rotation.length - 1"
              style="background:transparent; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:rgba(255,255,255,0.4); cursor:pointer; padding:3px 8px; font-size:13px;" :style="{ opacity: i >= rotation.length - 1 ? 0.3 : 1 }">↓</button>
            <button @click="removeFromRotation(entry.user_id)"
              style="background:transparent; border:1px solid rgba(244,63,94,0.25); border-radius:6px; color:rgba(244,63,94,0.6); cursor:pointer; padding:3px 8px; font-size:13px;">×</button>
          </div>
        </div>

        <!-- Nutzer hinzufügen -->
        <div v-if="usersNotInRotation().length > 0"
          style="background:#0d1117; border:1px solid rgba(255,255,255,0.12); border-radius:16px; padding:24px; margin-bottom:16px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">Hinzufügen</p>
          <div v-for="u in usersNotInRotation()" :key="u.id"
            style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
            <div>
              <p style="font-size:14px; font-weight:500; margin:0;">{{ u.name }}</p>
              <p style="font-size:11px; color:rgba(255,255,255,0.3); margin:2px 0 0;">{{ u.email }}</p>
            </div>
            <button @click="addToRotation(u)"
              style="background:transparent; border:1px solid rgba(255,255,255,0.15); border-radius:8px; color:rgba(255,255,255,0.6); cursor:pointer; padding:5px 14px; font-size:13px;">+ Hinzufügen</button>
          </div>
        </div>

        <p v-if="rotMsg" :style="{ fontSize:'13px', color: rotMsg.includes('✓') ? '#10b981' : '#f43f5e', marginBottom:'12px' }">{{ rotMsg }}</p>

        <button @click="saveRotation" :disabled="rotSaving"
          :style="{ width:'100%', padding:'11px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background:'#06b6d4', boxShadow:'0 0 20px rgba(6,182,212,0.3)', opacity: rotSaving ? 0.7 : 1 }">
          {{ rotSaving ? 'Speichern...' : 'Rotation speichern' }}
        </button>
      </div>
    </main>
  </div>
</template>
