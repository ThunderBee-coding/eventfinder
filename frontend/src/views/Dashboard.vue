<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import CreateEventModal from '../components/CreateEventModal.vue'

const { headers, logout } = useAuth()

interface Event {
  id: string; title: string; description?: string
  location_name?: string; accent_color: string
  cover_image_path?: string; is_closed: boolean
  final_date?: string; created_at: string
}

const events = ref<Event[]>([])
const loading = ref(true)
const showCreate = ref(false)

const fetchEvents = async () => {
  try {
    const res = await axios.get('/events/', { headers: headers() })
    events.value = res.data
  } catch { /* 401 handled by interceptor */ }
  finally { loading.value = false }
}

function onCreated(_id: string) {
  showCreate.value = false
  fetchEvents()
}

function cardHover(el: HTMLElement, accent: string, enter: boolean) {
  el.style.boxShadow = enter ? `0 0 35px ${accent}33` : 'none'
  el.style.borderColor = enter ? `${accent}44` : 'rgba(255,255,255,0.07)'
  el.style.transform = enter ? 'translateY(-2px)' : 'translateY(0)'
}

const router = useRouter()

const isAdmin = computed(() => {
  try {
    const token = localStorage.getItem('token') ?? ''
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role === 'superadmin'
  } catch { return false }
})

onMounted(fetchEvents)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <!-- Header -->
    <header style="border-bottom:1px solid var(--border); padding:16px 32px; display:flex; align-items:center; justify-content:space-between; backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; background:rgba(8,11,20,0.8);">
      <span style="font-weight:700; font-size:18px; letter-spacing:-0.5px;">EventFinder</span>
      <div style="display:flex; align-items:center; gap:12px;">
        <button @click="showCreate = true"
          style="display:flex; align-items:center; gap:6px; background:#06b6d4; color:#000; border:none; padding:9px 18px; border-radius:10px; font-weight:600; font-size:14px; cursor:pointer; box-shadow:0 0 20px rgba(6,182,212,0.4);">
          ＋ Neues Event
        </button>
        <button v-if="isAdmin" @click="router.push('/admin/settings')"
          style="background:transparent; border:1px solid rgba(255,255,255,0.1); color:rgba(255,255,255,0.5); padding:9px 12px; border-radius:10px; cursor:pointer; font-size:14px;"
          title="Einstellungen">
          ⚙️
        </button>
        <button @click="logout"
          style="background:transparent; border:1px solid var(--border); color:var(--text-secondary); padding:9px 14px; border-radius:10px; cursor:pointer; font-size:13px;">
          Abmelden
        </button>
      </div>
    </header>

    <main style="max-width:1100px; margin:0 auto; padding:40px 24px;">
      <div style="margin-bottom:32px;">
        <h1 style="font-size:28px; font-weight:700; letter-spacing:-0.5px; margin-bottom:4px;">Meine Events</h1>
        <p style="color:var(--text-secondary); font-size:14px;">{{ events.length }} {{ events.length === 1 ? 'Event' : 'Events' }}</p>
      </div>

      <div v-if="loading" style="text-align:center; color:var(--text-secondary); padding:60px 0;">
        Lade Events...
      </div>

      <div v-else-if="events.length === 0" style="text-align:center; padding:80px 0;">
        <div style="font-size:48px; margin-bottom:16px; opacity:0.3;">🗓️</div>
        <p style="color:var(--text-secondary); margin-bottom:24px;">Noch keine Events. Erstelle dein erstes!</p>
        <button @click="showCreate = true"
          style="background:#06b6d4; color:#000; border:none; padding:12px 28px; border-radius:12px; font-weight:600; cursor:pointer; font-size:15px;">
          ＋ Event erstellen
        </button>
      </div>

      <div v-else style="display:grid; grid-template-columns:repeat(auto-fill, minmax(290px,1fr)); gap:20px;">
        <router-link v-for="ev in events" :key="ev.id" :to="`/event/${ev.id}`"
          style="text-decoration:none; color:inherit; display:block; border-radius:18px; overflow:hidden; background:var(--bg-card); border:1px solid var(--border); transition:all .25s; cursor:pointer;"
          @mouseenter="e => cardHover(e.currentTarget as HTMLElement, ev.accent_color, true)"
          @mouseleave="e => cardHover(e.currentTarget as HTMLElement, ev.accent_color, false)">
          <!-- Cover -->
          <div style="height:110px; position:relative; overflow:hidden;">
            <img v-if="ev.cover_image_path" :src="`/${ev.cover_image_path}`"
              style="width:100%; height:100%; object-fit:cover;" />
            <div v-else :style="{ height:'100%', background:`linear-gradient(135deg, ${ev.accent_color}33, #080b14)` }" />
            <div style="position:absolute; inset:0; background:rgba(0,0,0,0.15);" />
            <div :style="{ position:'absolute', bottom:0, left:0, right:0, height:'1px', background:`linear-gradient(90deg, transparent, ${ev.accent_color}, transparent)` }" />
            <span :style="{
              position:'absolute', top:'10px', right:'10px', fontSize:'11px',
              padding:'3px 9px', borderRadius:'20px', background:'rgba(0,0,0,0.55)',
              backdropFilter:'blur(8px)', color: ev.accent_color, border:'1px solid rgba(255,255,255,0.08)'
            }">{{ ev.is_closed ? 'Abgeschlossen' : ev.final_date ? 'Datum festgelegt' : 'Abstimmung läuft' }}</span>
          </div>
          <!-- Body -->
          <div style="padding:18px;">
            <h2 style="font-size:17px; font-weight:600; margin-bottom:6px;">{{ ev.title }}</h2>
            <p style="color:var(--text-secondary); font-size:13px; margin-bottom:14px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
              {{ ev.description || 'Keine Beschreibung' }}
            </p>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-muted);">
              <span v-if="ev.location_name">📍 {{ ev.location_name }}</span>
              <span v-if="ev.final_date">📅 {{ new Date(ev.final_date).toLocaleDateString('de-DE') }}</span>
            </div>
          </div>
        </router-link>

        <!-- Add card -->
        <div @click="showCreate = true"
          style="border-radius:18px; border:1.5px dashed rgba(255,255,255,0.1); min-height:180px; display:flex; align-items:center; justify-content:center; cursor:pointer; transition:all .2s;"
          @mouseenter="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.25)' }"
          @mouseleave="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.1)' }">
          <div style="text-align:center;">
            <div style="font-size:30px; color:rgba(255,255,255,0.15); margin-bottom:8px;">＋</div>
            <p style="color:var(--text-muted); font-size:13px;">Event erstellen</p>
          </div>
        </div>
      </div>
    </main>

    <CreateEventModal v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>
