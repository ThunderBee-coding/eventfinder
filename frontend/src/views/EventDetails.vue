<!-- frontend/src/views/EventDetails.vue -->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import type { Map as LeafletMap, Marker } from 'leaflet'
import 'leaflet/dist/leaflet.css'
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

// --- Kalender-Einladung ---
const showCalendarModal = ref(false)
const calStartTime = ref('14:00')
const calEndTime = ref('16:00')
const calDescription = ref('')
const calSending = ref(false)
const calSent = ref(false)

async function sendCalendarInvites() {
  calSending.value = true
  try {
    await axios.post(`/events/${eventId}/send-invites`, {
      start_time: calStartTime.value,
      end_time: calEndTime.value,
      description: calDescription.value || null,
    }, { headers: headers() })
    calSent.value = true
    setTimeout(() => { showCalendarModal.value = false; calSent.value = false }, 2000)
  } catch (e: any) {
    console.error('Calendar invites failed', e)
  } finally {
    calSending.value = false
  }
}

// --- Orts-Editor (Leaflet + Nominatim) ---
const locationSearch = ref('')
const locationResults = ref<Array<{ display_name: string; lat: number; lon: number; bundesland: string }>>([])
let locationSearchTimeout: ReturnType<typeof setTimeout> | null = null
let mapInstance: LeafletMap | null = null
let mapMarker: Marker | null = null

// --- Task 10: Feiertage + Wetter ---
const holidays = ref<Record<string, string>>({})
const weatherHints = ref<Record<string, {
  temp_max_median: number | null
  temp_min_median: number | null
  precip_median: number | null
  loading: boolean
  forecast_temp_max: number | null
  forecast_temp_min: number | null
  forecast_code: number | null
}>>({})

async function loadWeatherHints() {
  if (!eventId) return
  try {
    const res = await axios.get(`/events/${eventId}/weather-hints`, { headers: headers() })
    const map: Record<string, any> = {}
    for (const h of res.data) map[h.date] = h
    weatherHints.value = map
  } catch (e) {
    console.error('Weather hints load failed', e)
  }
}

async function loadHolidays() {
  if (!eventId) return
  try {
    const years = [...new Set(proposals.value.map((p: any) => p.proposed_date.slice(0, 4)))]
    for (const year of years) {
      const res = await axios.get(`/events/${eventId}/holidays?year=${year}`, { headers: headers() })
      Object.assign(holidays.value, res.data)
    }
  } catch (e) {
    console.error('Holidays load failed', e)
  }
}

// --- Datums-Manager (nur Organisator) ---
const showDateManager = ref(false)
const dmFrom = ref('')
const dmTo = ref('')
const dmWeekdays = ref<number[]>([1, 2, 3, 4, 5]) // Mo–Fr default
const dmDates = ref<string[]>([])
const dmManualDate = ref('')
const dmSaving = ref(false)
const dmVotedDates = ref<string[]>([])  // Termine mit Abstimmungen die gelöscht würden
const WEEKDAY_LABELS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']

function dmGenerate() {
  if (!dmFrom.value || !dmTo.value) return
  const result: string[] = []
  // 'T00:00:00' erzwingt lokale Zeitzone statt UTC-Mitternacht
  const cur = new Date(dmFrom.value + 'T00:00:00')
  const end = new Date(dmTo.value + 'T00:00:00')
  while (cur <= end) {
    if (dmWeekdays.value.includes(cur.getDay())) {
      const y = cur.getFullYear()
      const m = String(cur.getMonth() + 1).padStart(2, '0')
      const d = String(cur.getDate()).padStart(2, '0')
      result.push(`${y}-${m}-${d}`)
    }
    cur.setDate(cur.getDate() + 1)
  }
  const merged = [...new Set([...dmDates.value, ...result])].sort()
  dmDates.value = merged
  dmVotedDates.value = []
}

function dmRemoveDate(d: string) {
  dmDates.value = dmDates.value.filter(x => x !== d)
  dmVotedDates.value = dmVotedDates.value.filter(x => x !== d)
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
  // Prüfen ob bereits bewertete Termine entfernt werden
  const newSet = new Set(dmDates.value)
  const voted = proposals.value
    .map((p: any) => p.proposed_date)
    .filter((d: string) => !newSet.has(d) && availabilities.value.some((a: any) => a.event_date === d))

  if (voted.length > 0 && dmVotedDates.value.length === 0) {
    dmVotedDates.value = voted
    return  // Warnung anzeigen, User muss nochmal klicken
  }
  dmVotedDates.value = []
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
  dmVotedDates.value = []
  showDateManager.value = true
}

function formatDateShort(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' })
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
  await Promise.all([loadHolidays(), loadWeatherHints()])
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

async function onLocationSearchInput() {
  if (locationSearchTimeout) clearTimeout(locationSearchTimeout)
  if (locationSearch.value.length < 3) {
    locationResults.value = []
    return
  }
  locationSearchTimeout = setTimeout(async () => {
    try {
      const res = await axios.get(`/geocode?q=${encodeURIComponent(locationSearch.value)}`, { headers: headers() })
      locationResults.value = res.data
    } catch (e) {
      console.error('Geocode search failed', e)
    }
  }, 300)
}

function selectLocation(result: { display_name: string; lat: number; lon: number }) {
  locationSearch.value = result.display_name
  locationResults.value = []
  if (mapInstance) {
    mapInstance.setView([result.lat, result.lon], 14)
    if (mapMarker) {
      mapMarker.setLatLng([result.lat, result.lon])
    } else {
      import('leaflet').then(L => {
        mapMarker = L.marker([result.lat, result.lon]).addTo(mapInstance!)
      })
    }
  }
}

async function saveLocation() {
  if (!locationSearch.value) return
  try {
    await axios.patch(`/events/${eventId}`, { address: locationSearch.value }, { headers: headers() })
    locationResults.value = []
    await load()
    await loadWeatherHints()
  } catch (e) {
    console.error('Save location failed', e)
  }
}

async function initMap(elementId: string, lat?: number, lon?: number) {
  const L = await import('leaflet')
  // Fix Leaflet default icon path in Vite
  delete (L.Icon.Default.prototype as any)._getIconUrl
  L.Icon.Default.mergeOptions({
    iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
    iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
    shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
  })
  const el = document.getElementById(elementId)
  if (!el) return null
  const center: [number, number] = lat && lon ? [lat, lon] : [48.137, 11.576]
  const zoom = lat && lon ? 13 : 5
  const m = L.map(el, { zoomControl: true }).setView(center, zoom)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO'
  }).addTo(m)
  if (lat && lon) {
    L.marker([lat, lon]).addTo(m)
  }
  return m
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

onBeforeUnmount(() => {
  // Leaflet-Instanz sauber zerstören um "already initialized"-Fehler bei Rückkehr zu vermeiden
  try { mapInstance?.remove() } catch (_) { /* ignore */ }
  mapInstance = null
  mapMarker = null
})

onMounted(async () => {
  await load()
  if (!event.value) return  // load() fehlgeschlagen — kein Map-Init nötig

  try {
    if (event.value?.latitude && !isOrganizer.value) {
      await nextTick()
      mapInstance = await initMap('event-readonly-map', event.value.latitude, event.value.longitude) as any
    }
    if (isOrganizer.value) {
      await nextTick()
      locationSearch.value = event.value?.address || event.value?.location_name || ''
      mapInstance = await initMap('event-location-map', event.value?.latitude, event.value?.longitude) as any
      if (mapInstance && event.value?.latitude && event.value?.longitude) {
        const L = await import('leaflet')
        mapMarker = L.marker([event.value.latitude, event.value.longitude]).addTo(mapInstance)
      }
    }
  } catch (e) {
    console.error('Map init failed:', e)  // Leaflet-Fehler blockieren nicht den Rest der Seite
  }
})
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

    <div v-else-if="!event" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:60vh; gap:16px; color:var(--text-secondary);">
      <p style="font-size:18px;">Event konnte nicht geladen werden.</p>
      <p style="font-size:14px; opacity:0.6;">Möglicherweise bist du nicht Teilnehmer dieses Events oder deine Sitzung ist abgelaufen.</p>
      <router-link to="/" style="color:#06b6d4; text-decoration:none; border:1px solid rgba(6,182,212,0.3); padding:10px 20px; border-radius:10px; font-size:14px;">← Zurück zum Dashboard</router-link>
    </div>

    <main v-else style="max-width:1000px; margin:0 auto; padding:32px 24px;">
      <EventHero
        :title="event.title"
        :description="event.description"
        :location-name="event.location_name"
        :address="event.address"
        :accent-color="event.accent_color"
        :cover-image-path="event.cover_image_path"
        :participant-count="participants.length"
        :is-organizer="isOrganizer"
        @invite="showInvite = true"
        @edit-cover="showCoverUpload = true"
        @edit-location="locationSearch = event.address || event.location_name || ''"
        @update-location="updateLocation"
        style="margin-bottom:28px;"
      />

      <!-- ORTS-EDITOR (nur für Organizer) -->
      <div v-if="isOrganizer" style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px;">

        <!-- Ort-Editor -->
        <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px;">📍 Veranstaltungsort</p>
          <div style="position:relative; margin-bottom:12px;">
            <input
              v-model="locationSearch"
              @input="onLocationSearchInput"
              placeholder="Adresse oder Ort eingeben…"
              style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:9px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;"
            />
            <div v-if="locationResults.length > 0"
              style="position:absolute; top:100%; left:0; right:0; background:#1a2035; border:1px solid rgba(255,255,255,0.12); border-radius:10px; margin-top:4px; overflow:hidden; z-index:100;">
              <div v-for="r in locationResults" :key="r.display_name"
                @click="selectLocation(r)"
                style="padding:10px 14px; font-size:13px; cursor:pointer; border-bottom:1px solid rgba(255,255,255,0.05);"
                @mouseenter="(e) => ((e.currentTarget as HTMLElement).style.background='rgba(6,182,212,0.1)')"
                @mouseleave="(e) => ((e.currentTarget as HTMLElement).style.background='transparent')">
                <strong style="display:block; color:#fff; font-size:13px;">{{ r.display_name.split(',')[0] }}</strong>
                <span style="color:rgba(255,255,255,0.45); font-size:11px;">{{ r.display_name.split(',').slice(1).join(',').trim() }}</span>
              </div>
            </div>
          </div>
          <div id="event-location-map" style="height:160px; border-radius:12px; border:1px solid rgba(255,255,255,0.07); margin-bottom:12px;"></div>
          <div style="display:flex; justify-content:flex-end; gap:8px;">
            <button @click="locationSearch = ''; locationResults = []"
              style="padding:7px 14px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.5); cursor:pointer; font-size:12px;">
              Zurücksetzen
            </button>
            <button @click="saveLocation" :disabled="!locationSearch"
              :style="{ padding:'7px 14px', borderRadius:'10px', border:'none', fontWeight:600, fontSize:'12px', color:'#000',
                background: event?.accent_color || '#06b6d4',
                cursor: locationSearch ? 'pointer' : 'not-allowed',
                opacity: locationSearch ? 1 : 0.5 }">
              Ort speichern
            </button>
          </div>
        </div>

        <!-- ZEITRAUM-EDITOR -->
        <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px;">📅 Zeitraum &amp; Termine</p>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px;">
            <div>
              <label style="font-size:11px;color:rgba(255,255,255,0.35);display:block;margin-bottom:5px;">Von</label>
              <input type="date" v-model="dmFrom"
                style="width:100%;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:8px 12px;color:#fff;font-size:13px;outline:none;color-scheme:dark;box-sizing:border-box;" />
            </div>
            <div>
              <label style="font-size:11px;color:rgba(255,255,255,0.35);display:block;margin-bottom:5px;">Bis</label>
              <input type="date" v-model="dmTo"
                style="width:100%;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:8px 12px;color:#fff;font-size:13px;outline:none;color-scheme:dark;box-sizing:border-box;" />
            </div>
          </div>

          <label style="font-size:11px;color:rgba(255,255,255,0.35);display:block;margin-bottom:8px;">Wochentage</label>
          <div style="display:flex;gap:5px;margin-bottom:12px;flex-wrap:wrap;">
            <button v-for="(label, i) in WEEKDAY_LABELS" :key="i" @click="dmToggleDay(i)"
              :style="{
                padding:'4px 10px', borderRadius:'7px', border:'1px solid', cursor:'pointer', fontSize:'12px',
                borderColor: dmWeekdays.includes(i) ? `${event.accent_color}88` : 'rgba(255,255,255,0.1)',
                background: dmWeekdays.includes(i) ? `${event.accent_color}18` : 'transparent',
                color: dmWeekdays.includes(i) ? '#fff' : 'rgba(255,255,255,0.35)',
                fontWeight: dmWeekdays.includes(i) ? '500' : '400',
              }">{{ label }}</button>
          </div>

          <button @click="dmGenerate"
            :style="{ width:'100%', padding:'8px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px', color:'#000', background: event.accent_color, marginBottom:'12px' }">
            Termine generieren
          </button>

          <!-- Vorschau -->
          <div v-if="dmDates.length > 0" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;margin-bottom:12px;">
            <p style="font-size:11px;color:rgba(255,255,255,0.3);margin:0 0 8px;">{{ dmDates.length }} Termine</p>
            <div style="display:flex;flex-wrap:wrap;gap:5px;max-height:100px;overflow-y:auto;">
              <span v-for="d in dmDates" :key="d"
                :style="{
                  background: holidays?.[d] ? 'rgba(249,115,22,0.12)' : 'rgba(6,182,212,0.1)',
                  border: `1px solid ${holidays?.[d] ? 'rgba(249,115,22,0.3)' : 'rgba(6,182,212,0.25)'}`,
                  borderRadius:'6px', padding:'3px 8px', fontSize:'11px',
                  color: holidays?.[d] ? '#f97316' : '#06b6d4',
                  display:'flex', alignItems:'center', gap:'4px',
                }">
                {{ formatDateShort(d) }}{{ holidays?.[d] ? ' 🎉' : '' }}
                <button @click="dmRemoveDate(d)" style="background:none;border:none;color:rgba(244,63,94,0.6);cursor:pointer;font-size:13px;padding:0;line-height:1;">×</button>
              </span>
            </div>
          </div>
          <p v-if="dmDates.length === 0 && (dmFrom || dmTo)" style="font-size:12px;color:rgba(255,255,255,0.25);margin:0 0 12px;">Noch keine Termine generiert.</p>

          <p style="font-size:11px;color:rgba(249,115,22,0.6);margin:0 0 12px;">🎉 Feiertage werden markiert, aber nicht ausgeschlossen</p>

          <!-- Warnung: bewertete Termine werden gelöscht -->
          <div v-if="dmVotedDates.length > 0"
            style="background:rgba(244,63,94,0.1);border:1px solid rgba(244,63,94,0.35);border-radius:10px;padding:10px 12px;margin-bottom:12px;">
            <p style="font-size:12px;color:#f43f5e;margin:0 0 6px;font-weight:600;">⚠ Diese Termine haben bereits Abstimmungen und werden gelöscht:</p>
            <p style="font-size:11px;color:rgba(244,63,94,0.8);margin:0 0 8px;">{{ dmVotedDates.map(d => formatDateShort(d)).join(' · ') }}</p>
            <p style="font-size:11px;color:rgba(255,255,255,0.4);margin:0;">Nochmals auf "Speichern" klicken um trotzdem fortzufahren.</p>
          </div>

          <div style="display:flex;justify-content:flex-end;gap:8px;">
            <button @click="dmDates = []; dmVotedDates = []"
              style="padding:7px 14px;border-radius:10px;background:transparent;border:1px solid rgba(255,255,255,0.12);color:rgba(255,255,255,0.5);cursor:pointer;font-size:12px;">
              Leeren
            </button>
            <button @click="dmSave" :disabled="dmSaving || dmDates.length === 0"
              :style="{ padding:'7px 16px', borderRadius:'10px', border:'none', fontWeight:600, fontSize:'12px', color:'#000',
                background: dmVotedDates.length > 0 ? '#f43f5e' : event.accent_color,
                cursor: dmDates.length > 0 ? 'pointer' : 'not-allowed',
                opacity: dmDates.length === 0 ? 0.5 : 1 }">
              {{ dmSaving ? 'Speichern…' : dmVotedDates.length > 0 ? '⚠ Trotzdem speichern' : `${dmDates.length} Termine speichern` }}
            </button>
          </div>
        </div>

      </div>

      <!-- KARTE (read-only, für alle wenn Koordinaten vorhanden) -->
      <div v-if="event?.latitude && !isOrganizer"
        style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; overflow:hidden; margin-bottom:20px; height:180px;">
        <div id="event-readonly-map" style="height:100%;"></div>
      </div>

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
              :participants="participants"
              :participant-count="participants.length"
              :accent-color="event.accent_color"
              :final-date="event.final_date"
              :is-organizer="isOrganizer"
              :holidays="holidays"
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

          <!-- Kalender-Einladung (nur Organisator + finales Datum gesetzt) -->
          <div v-if="isOrganizer && event.final_date"
            style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <p style="font-size:11px; color:rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:.08em; margin-bottom:12px;">📅 Termin bestätigt</p>
            <p style="font-size:14px; font-weight:600; margin-bottom:4px;">
              {{ new Date(event.final_date + 'T00:00:00').toLocaleDateString('de-DE', { weekday:'long', day:'numeric', month:'long', year:'numeric' }) }}
            </p>
            <p style="font-size:13px; color:rgba(255,255,255,0.4); margin-bottom:16px;">Sende eine Kalender-Einladung (ICS) an alle Teilnehmer.</p>
            <button @click="showCalendarModal = true"
              :style="{ width:'100%', padding:'10px', borderRadius:'12px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px', color:'#000', background: event.accent_color, boxShadow: `0 0 20px ${event.accent_color}44` }">
              📅 Kalender-Einladung versenden
            </button>
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
            :holidays="holidays"
            :weather-hints="weatherHints"
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

        <!-- Warnung: bewertete Termine werden gelöscht -->
        <div v-if="dmVotedDates.length > 0"
          style="background:rgba(244,63,94,0.1);border:1px solid rgba(244,63,94,0.35);border-radius:10px;padding:12px 14px;margin-bottom:16px;">
          <p style="font-size:13px;color:#f43f5e;margin:0 0 6px;font-weight:600;">⚠ Diese Termine haben bereits Abstimmungen:</p>
          <p style="font-size:12px;color:rgba(244,63,94,0.8);margin:0 0 8px;">{{ dmVotedDates.map(d => formatDateShort(d)).join(' · ') }}</p>
          <p style="font-size:12px;color:rgba(255,255,255,0.4);margin:0;">Nochmals auf "Speichern" klicken um trotzdem fortzufahren.</p>
        </div>

        <!-- Aktionen -->
        <div style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showDateManager = false; dmVotedDates = []"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
          <button @click="dmSave" :disabled="dmSaving || dmDates.length === 0"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000',
              background: dmVotedDates.length > 0 ? '#f43f5e' : event.accent_color,
              opacity: (dmSaving || dmDates.length === 0) ? 0.6 : 1 }">
            {{ dmSaving ? 'Speichern...' : dmVotedDates.length > 0 ? '⚠ Trotzdem speichern' : `${dmDates.length} Termine speichern` }}
          </button>
        </div>
      </div>
    </div>

    <InviteModal v-if="showInvite" :event-id="eventId" :accent-color="event?.accent_color ?? '#06b6d4'"
      @close="showInvite = false" @invited="load()" />

    <!-- Kalender-Einladung Modal -->
    <div v-if="showCalendarModal"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showCalendarModal = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:420px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:6px;">📅 Kalender-Einladung</h2>
        <p style="color:rgba(255,255,255,0.4); font-size:13px; margin-bottom:24px;">
          Wird an alle {{ participants.length }} Teilnehmer gesendet.
        </p>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
          <div>
            <label style="font-size:11px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Beginn</label>
            <input type="time" v-model="calStartTime"
              style="width:100%; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 12px; color:#fff; font-size:14px; outline:none; color-scheme:dark; box-sizing:border-box;" />
          </div>
          <div>
            <label style="font-size:11px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Ende</label>
            <input type="time" v-model="calEndTime"
              style="width:100%; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 12px; color:#fff; font-size:14px; outline:none; color-scheme:dark; box-sizing:border-box;" />
          </div>
        </div>

        <label style="font-size:11px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">
          Beschreibung im Kalendereintrag <span style="color:rgba(255,255,255,0.2);">(optional)</span>
        </label>
        <textarea v-model="calDescription" rows="4"
          :placeholder="`z.B. Bringt eure Lieblings-Spiele mit! Treffpunkt: Eingang Marienplatz.`"
          style="width:100%; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:20px; box-sizing:border-box; resize:vertical; font-family:inherit;"></textarea>

        <div v-if="calSent" style="text-align:center; color:#10b981; font-size:15px; padding:8px 0;">
          ✓ Einladungen werden versendet!
        </div>
        <div v-else style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showCalendarModal = false"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
          <button @click="sendCalendarInvites" :disabled="calSending"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor: calSending ? 'default' : 'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event?.accent_color ?? '#06b6d4', opacity: calSending ? 0.7 : 1 }">
            {{ calSending ? 'Sende…' : `📅 An ${participants.length} Teilnehmer senden` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
