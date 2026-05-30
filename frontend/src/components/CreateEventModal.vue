<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const emit = defineEmits<{ close: []; created: [id: string] }>()
const { headers } = useAuth()

const ACCENTS = ['#06b6d4','#8b5cf6','#f43f5e','#f59e0b','#10b981']

const form = ref({ title: '', description: '', location_name: '', accent_color: '#06b6d4' })
const proposedDates = ref<string[]>([''])
const coverFile = ref<File | null>(null)
const coverPreview = ref('')
const loading = ref(false)
const error = ref('')

function addDate() { if (proposedDates.value.length < 5) proposedDates.value.push('') }
function removeDate(i: number) { proposedDates.value.splice(i, 1) }

function onFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (f.size > 5 * 1024 * 1024) { error.value = 'Bild darf max. 5 MB groß sein'; return }
  coverFile.value = f
  coverPreview.value = URL.createObjectURL(f)
}

async function submit() {
  error.value = ''
  if (!form.value.title.trim()) { error.value = 'Titel ist erforderlich'; return }
  const validDates = proposedDates.value.filter(d => d)
  if (validDates.length === 0) { error.value = 'Mindestens ein Datumsvorschlag erforderlich'; return }
  loading.value = true
  try {
    const res = await axios.post('/events/', { ...form.value, proposed_dates: validDates }, { headers: headers() })
    if (coverFile.value) {
      const fd = new FormData()
      fd.append('file', coverFile.value)
      await axios.post(`/events/${res.data.id}/cover`, fd, { headers: { ...headers(), 'Content-Type': 'multipart/form-data' } })
    }
    emit('created', res.data.id)
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Fehler beim Erstellen'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);" @click.self="emit('close')">
    <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:520px; max-height:90vh; overflow-y:auto;">
      <h2 style="font-size:20px; font-weight:700; margin-bottom:24px;">Neues Event erstellen</h2>
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Titel *</label>
          <input v-model="form.title" placeholder="z.B. Sommerfest 🌞" style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
        </div>
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Beschreibung</label>
          <textarea v-model="form.description" rows="2" placeholder="Worum geht es?" style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; resize:none; box-sizing:border-box;" />
        </div>
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Ort</label>
          <input v-model="form.location_name" placeholder="z.B. München, Olympiastadion" style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
        </div>
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Akzentfarbe</label>
          <div style="display:flex; gap:10px;">
            <button v-for="c in ACCENTS" :key="c" @click="form.accent_color = c" :style="{ width:'28px', height:'28px', borderRadius:'50%', border:'none', cursor:'pointer', background: c, boxShadow: form.accent_color === c ? `0 0 14px ${c}` : 'none', transform: form.accent_color === c ? 'scale(1.25)' : 'scale(1)', transition:'all .2s' }" />
          </div>
        </div>
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Datumsvorschläge * (1–5)</label>
          <div v-for="(d, i) in proposedDates" :key="i" style="display:flex; gap:8px; margin-bottom:8px;">
            <input type="date" v-model="proposedDates[i]" style="flex:1; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:9px 12px; color:#fff; font-size:14px; outline:none; color-scheme:dark;" />
            <button v-if="proposedDates.length > 1" @click="removeDate(i)" style="background:rgba(244,63,94,0.15); border:1px solid rgba(244,63,94,0.3); color:#f43f5e; width:36px; border-radius:8px; cursor:pointer; font-size:16px;">×</button>
          </div>
          <button v-if="proposedDates.length < 5" @click="addDate" style="font-size:13px; color:rgba(255,255,255,0.4); background:transparent; border:1px dashed rgba(255,255,255,0.15); padding:7px 14px; border-radius:8px; cursor:pointer;">+ Datum hinzufügen</button>
        </div>
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Cover-Bild (optional, max 5 MB)</label>
          <div v-if="coverPreview" style="margin-bottom:8px;"><img :src="coverPreview" style="width:100%; height:100px; object-fit:cover; border-radius:10px;" /></div>
          <input type="file" accept="image/jpeg,image/png,image/webp" @change="onFileChange" style="width:100%; background:rgba(255,255,255,0.04); border:1px dashed rgba(255,255,255,0.15); border-radius:10px; padding:10px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer; box-sizing:border-box;" />
        </div>
      </div>
      <p v-if="error" style="color:#f43f5e; font-size:13px; margin-top:16px;">{{ error }}</p>
      <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:24px;">
        <button @click="emit('close')" style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
        <button @click="submit" :disabled="loading" :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: form.accent_color, boxShadow: `0 0 20px ${form.accent_color}66`, opacity: loading ? 0.7 : 1 }">{{ loading ? 'Erstelle...' : 'Event erstellen' }}</button>
      </div>
    </div>
  </div>
</template>
