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

async function load() {
  try {
    const token = localStorage.getItem('token') ?? ''
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      myUserId.value = payload.sub
    } catch (e) {
      console.error('JWT decode failed:', e)
      return
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

const allAvailabilities = computed(() =>
  availabilities.value.map((a: any) => ({ ...a, own: true }))
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
        style="margin-bottom:28px;"
      />

      <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
        <!-- Left -->
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <DateProposals
              :proposals="proposals"
              :availabilities="allAvailabilities"
              :participant-count="participants.length"
              :accent-color="event.accent_color"
              :final-date="event.final_date"
              @set-final="isOrganizer && setFinalDate($event)"
            />
          </div>
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <ParticipantList
              :participants="participants"
              :accent-color="event.accent_color"
              :total-proposals="proposals.length"
              @invite="showInvite = true"
            />
          </div>
        </div>

        <!-- Right: Calendar -->
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

    <!-- Availability Modal -->
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
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
            Abbrechen
          </button>
          <button @click="saveAvailability"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event.accent_color }">
            Speichern
          </button>
        </div>
      </div>
    </div>

    <!-- Cover upload modal -->
    <div v-if="showCoverUpload"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showCoverUpload = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:400px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:16px;">Cover-Bild hochladen</h2>
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadCover"
          style="width:100%; background:rgba(255,255,255,0.04); border:1.5px dashed rgba(255,255,255,0.15); border-radius:10px; padding:14px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer; box-sizing:border-box;" />
        <p style="color:var(--text-muted); font-size:12px; margin-top:10px;">JPEG, PNG oder WebP · max. 5 MB</p>
        <button @click="showCoverUpload = false"
          style="margin-top:16px; padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
          Abbrechen
        </button>
      </div>
    </div>

    <InviteModal v-if="showInvite" :event-id="eventId" :accent-color="event?.accent_color ?? '#06b6d4'"
      @close="showInvite = false" @invited="load()" />
  </div>
</template>
