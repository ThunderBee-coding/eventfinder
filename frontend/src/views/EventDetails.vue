<!-- frontend/src/views/EventDetails.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'
import EventHero from '../components/EventHero.vue'
import AvailabilityCalendar from '../components/AvailabilityCalendar.vue'
import DateProposals from '../components/DateProposals.vue'
import ParticipantList from '../components/ParticipantList.vue'
import InviteModal from '../components/InviteModal.vue'

const route = useRoute()
const { headers } = useAuth()
const eventId = route.params.id as string

const event = ref<any>(null)
const participants = ref<any[]>([])
const proposals = ref<any[]>([])
const availabilities = ref<any[]>([])
const myUserId = ref<string | null>(null)
const loading = ref(true)
const showInvite = ref(false)
const showAvailModal = ref(false)
const selectedDate = ref('')
const availStatus = ref<'best'|'possible'|'impossible'>('possible')
const availComment = ref('')
const showCoverUpload = ref(false)

// --- Datums-Manager (nur Organisator) ---
const showDateManager = ref(false)
const dmFrom = ref('')
const dmTo = ref('')
const dmWeekdays = ref<number[]>([1, 2, 3, 4, 5]) // Mo–Fr default
const dmDates = ref<string[]>([])
const dmManualDate = ref('')
const dmSaving = ref(false)
const WEEKDAY_LABELS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']

function dmGenerate() {
  if (!dmFrom.value || !dmTo.value) return
  const result: string[] = []
  const cur = new Date(dmFrom.value)
  const end = new Date(dmTo.value)
  while (cur <= end) {
    if (dmWeekdays.value.includes(cur.getDay())) {
      result.push(cur.toISOString().slice(0, 10))
    }
    cur.setDate(cur.getDate() + 1)
  }
  // Merge mit bereits manuell ausgewählten (kein Duplikat)
  const merged = [...new Set([...dmDates.value, ...result])].sort()
  dmDates.value = merged
}

function dmRemoveDate(d: string) {
  dmDates.value = dmDates.value.filter(x => x !== d)
}

function dmAddManual() {
  if (!dmManualDate.value) return
  if (!dmDates.value.includes(dmManualDate.value)) {
    dmDates.value = [...dmDates.value, dmManualDate.value].sort()
  }
  dmManualDate.value = ''
}

function dmToggleDay(day: number) {
  const idx = dmWeekdays.value.indexOf(day)
  if (idx >= 0) dmWeekdays.value.splice(idx, 1)
  else dmWeekdays.value.push(day)
}

async function dmSave() {
  dmSaving.value = true
  try {
    await axios.post(`/events/${eventId}/proposals`, { dates: dmDates.value }, { headers: headers() })
    showDateManager.value = false
    await load()
  } finally {
    dmSaving.value = false
  }
}

function dmOpen() {
  dmDates.value = proposals.value.map((p: any) => p.proposed_date)
  showDateManager.value = true
}

function formatDateShort(iso: string) {
  return new Date(iso).toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' })
}

// --- Laden ---
async function load() {
  try {
    const token = localStorage.getItem('token') ?? ''
    try {
      const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
      const payload = JSON.parse(atob(b64))
      myUserId.value = payload.sub
    } catch (e) {
      console.error('JWT decode failed:', e)
      // kein return — API-Calls laufen weiter, myUserId bleibt null
    }

    const [evRes, pRes, propRes, avRes] = await Promise.all([
      axios.get(`/events/${eventId}`, { headers: headers() }),
      axios.get(`/events/${eventId}/participants`, { headers: headers() }),
      axios.get(`/events/${eventId}/proposals`, { headers: headers() }),
      axios.get(`/events/${eventId}/availability`, { headers: headers() }),
    ])
    event.value = evRes.data
    participants.value = pRes.data
    proposals.value = propRes.data
    availabilities.value = avRes.data
  } catch (error) {
    console.error('Failed to load event:', error)
  } finally {
    loading.value = false
  }
}

const isOrganizer = computed(() => event.value?.organizer_id === myUserId.value)
const proposedDateStrings = computed(() => proposals.value.map((p: any) => p.proposed_date))
const myParticipantId = computed(() =>
  participants.value.find((p: any) => p.id === myUserId.value)?.participant_id
)
const allAvailabilities = computed(() =>
  availabilities.value.map((a: any) => ({ ...a, own: String(a.participant_id) === String(myParticipantId.value) }))
)

function onDateClick(date: string) {
  selectedDate.value = date
  const existing = availabilities.value.find((a: any) => a.event_date === date)
  availStatus.value = existing?.status ?? 'possible'
  availComment.value = existing?.comment ?? ''
  showAvailModal.value = true
}

async function saveAvailability() {
  await axios.post(`/events/${eventId}/availability`, {
    event_date: selectedDate.value, status: availStatus.value, comment: availComment.value,
  }, { headers: headers() })
  showAvailModal.value = false
  await load()
}

async function setFinalDate(date: string) {
  await axios.patch(`/events/${eventId}`, { final_date: date }, { headers: headers() })
  await load()
}

async function uploadCover(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    await axios.post(`/events/${eventId}/cover`, fd, { headers: headers() })
    showCoverUpload.value = false
    await load()
  } catch (error) {
    console.error('Cover upload failed:', error)
  }
}

async function updateLocation(value: string) {
  await axios.patch(`/events/${eventId}`, { location_name: value || null }, { headers: headers() })
  await load()
}

async function deleteParticipant(userId: string) {
  if (!confirm('Teilnehmer wirklich entfernen?')) return
  await axios.delete(`/events/${eventId}/participants/${userId}`, { headers: headers() })
  await load()
}

async function transferOrganizer(userId: string) {
  const p = participants.value.find((x: any) => x.id === userId)
  if (!confirm(`${p?.name ?? 'Diese Person'} zum Organisator machen?`)) return
  await axios.patch(`/events/${eventId}/organizer`, { user_id: userId }, { headers: headers() })
  await load()
}

onMounted(load)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <!-- Back nav -->
    <div style="padding:16px 32px; border-bottom:1px solid var(--border); background:rgba(8,11,20,0.8); backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:12px;">
      <router-link to="/" style="color:var(--text-secondary); text-decoration:none; font-size:14px;">← Dashboard</router-link>
      <span style="color:var(--border);">|</span>
      <span style="font-weight:600; font-size:14px;">{{ event?.title ?? '...' }}</span>
    </div>

    <div v-if="loading" style="display:flex; align-items:center; justify-content:center; height:60vh; color:var(--text-secondary);">
      Lade Event...
    </div>

    <main v-else-if="event" style="max-width:1000px; margin:0 auto; padding:32px 24px;">
      <EventHero
        :title="event.title"
        :description="event.description"
        :location-name="event.location_name"
        :accent-color="event.accent_color"
        :cover-image-path="event.cover_image_path"
        :participant-count="participants.length"
        :is-organizer="isOrganizer"
        @invite="showInvite = true"
        @edit-cover="showCoverUpload = true"
        @update-location="updateLocation"
        style="margin-bottom:28px;"
      />

      <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
        <!-- Links -->
        <div style="display:flex; flex-direction:column; gap:16px;">

          <!-- Datumsvorschläge -->
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
              <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin:0;">Datumsvorschläge</p>
              <button v-if="isOrganizer" @click="dmOpen"
                :style="{ fontSize:'12px', color: event.accent_color, background:'transparent', border:`1px solid ${event.accent_color}44`, borderRadius:'6px', padding:'3px 10px', cursor:'pointer' }">
                ✏ Termine
              </button>
            </div>
            <DateProposals
              :proposals="proposals"
              :availabilities="allAvailabilities"
              :participant-count="participants.length"
              :accent-color="event.accent_color"
              :final-date="event.final_date"
              :is-organizer="isOrganizer"
              @set-final="setFinalDate($event)"
            />
          </div>

          <!-- Teilnehmer -->
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <ParticipantList
              :participants="participants"
              :accent-color="event.accent_color"
              :total-proposals="proposals.length"
              :is-organizer="isOrganizer"
              :organizer-id="event.organizer_id"
              :my-user-id="myUserId ?? undefined"
              @invite="showInvite = true"
              @delete="deleteParticipant"
              @transfer-organizer="transferOrganizer"
            />
          </div>
        </div>

        <!-- Rechts: Kalender -->
        <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:24px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px;">
            Verfügbarkeit abstimmen
          </p>
          <p style="font-size:13px; color:var(--text-secondary); margin-bottom:20px;">
            Klicke auf einen vorgeschlagenen Termin um deine Verfügbarkeit anzugeben.
          </p>
          <AvailabilityCalendar
            :proposed-dates="proposedDateStrings"
            :availabilities="allAvailabilities"
            :participant-count="participants.length"
            :accent-color="event.accent_color"
            :final-date="event.final_date"
            @date-click="onDateClick"
          />
        </div>
      </div>
    </main>

    <!-- Verfügbarkeits-Modal -->
    <div v-if="showAvailModal"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showAvailModal = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:380px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:6px;">Verfügbarkeit</h2>
        <p style="color:var(--text-secondary); font-size:14px; margin-bottom:20px;">{{ selectedDate }}</p>
        <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
          <button v-for="opt in [{ v:'best', l:'🟢 Sehr gut / Favorit' },{ v:'possible', l:'🟡 Möglich' },{ v:'impossible', l:'🔴 Nicht möglich' }]"
            :key="opt.v" @click="availStatus = opt.v as any"
            :style="{
              padding:'11px 16px', borderRadius:'10px', border:'1px solid',
              borderColor: availStatus === opt.v ? `${event.accent_color}88` : 'rgba(255,255,255,0.1)',
              background: availStatus === opt.v ? `${event.accent_color}18` : 'transparent',
              color: availStatus === opt.v ? '#fff' : 'rgba(255,255,255,0.6)',
              cursor:'pointer', textAlign:'left', fontSize:'14px', fontWeight: availStatus === opt.v ? 600 : 400,
            }">{{ opt.l }}</button>
        </div>
        <input v-model="availComment" placeholder="Kommentar (optional)"
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:20px; box-sizing:border-box;" />
        <div style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showAvailModal = false"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
          <button @click="saveAvailability"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event.accent_color }">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Cover-Upload-Modal -->
    <div v-if="showCoverUpload"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showCoverUpload = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:400px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:16px;">Cover-Bild hochladen</h2>
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadCover"
          style="width:100%; background:rgba(255,255,255,0.04); border:1.5px dashed rgba(255,255,255,0.15); border-radius:10px; padding:14px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer; box-sizing:border-box;" />
        <p style="color:var(--text-muted); font-size:12px; margin-top:10px;">JPEG, PNG oder WebP · max. 5 MB</p>
        <button @click="showCoverUpload = false"
          style="margin-top:16px; padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
      </div>
    </div>

    <!-- Datums-Manager-Modal -->
    <div v-if="showDateManager"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showDateManager = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:520px; max-height:90vh; overflow-y:auto;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:20px;">Termine verwalten</h2>

        <!-- Schritt 1: Zeitraum + Wochentage -->
        <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px;">1 — Zeitraum festlegen</p>
        <div style="display:flex; gap:10px; margin-bottom:12px;">
          <div style="flex:1;">
            <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:5px;">Von</label>
            <input type="date" v-model="dmFrom" style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:8px 12px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; color-scheme:dark;" />
          </div>
          <div style="flex:1;">
            <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:5px;">Bis</label>
            <input type="date" v-model="dmTo" style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:8px 12px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; color-scheme:dark;" />
          </div>
        </div>

        <!-- Wochentage -->
        <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px;">Wochentage</p>
        <div style="display:flex; gap:6px; margin-bottom:14px; flex-wrap:wrap;">
          <button
            v-for="(label, i) in WEEKDAY_LABELS" :key="i"
            @click="dmToggleDay(i)"
            :style="{
              padding:'5px 12px', borderRadius:'8px', border:'1px solid', cursor:'pointer', fontSize:'13px', fontWeight:500,
              borderColor: dmWeekdays.includes(i) ? `${event.accent_color}99` : 'rgba(255,255,255,0.1)',
              background: dmWeekdays.includes(i) ? `${event.accent_color}22` : 'transparent',
              color: dmWeekdays.includes(i) ? '#fff' : 'rgba(255,255,255,0.4)',
            }">{{ label }}</button>
        </div>

        <button @click="dmGenerate"
          :style="{ width:'100%', padding:'9px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event.accent_color, marginBottom:'20px' }">
          Termine generieren
        </button>

        <!-- Schritt 2: Ergebnis anpassen -->
        <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px;">2 — Ergebnis anpassen ({{ dmDates.length }} Termine)</p>

        <!-- Tags -->
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; min-height:32px;">
          <span v-for="d in dmDates" :key="d"
            style="display:flex; align-items:center; gap:5px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:4px 10px; font-size:13px;">
            {{ formatDateShort(d) }}
            <button @click="dmRemoveDate(d)" style="background:none; border:none; color:rgba(244,63,94,0.7); cursor:pointer; font-size:14px; padding:0; line-height:1;">×</button>
          </span>
          <span v-if="dmDates.length === 0" style="color:rgba(255,255,255,0.2); font-size:13px; align-self:center;">Noch keine Termine</span>
        </div>

        <!-- Einzeln hinzufügen -->
        <div style="display:flex; gap:8px; margin-bottom:24px;">
          <input type="date" v-model="dmManualDate"
            style="flex:1; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:8px 12px; color:#fff; font-size:14px; outline:none; color-scheme:dark;" />
          <button @click="dmAddManual"
            style="padding:8px 16px; border-radius:8px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); color:rgba(255,255,255,0.7); cursor:pointer; font-size:14px; white-space:nowrap;">
            + Datum
          </button>
        </div>

        <!-- Aktionen -->
        <div style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showDateManager = false"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
          <button @click="dmSave" :disabled="dmSaving || dmDates.length === 0"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event.accent_color, opacity: (dmSaving || dmDates.length === 0) ? 0.6 : 1 }">
            {{ dmSaving ? 'Speichern...' : `${dmDates.length} Termine speichern` }}
          </button>
        </div>
      </div>
    </div>

    <InviteModal v-if="showInvite" :event-id="eventId" :accent-color="event?.accent_color ?? '#06b6d4'"
      @close="showInvite = false" @invited="load()" />
  </div>
</template>
