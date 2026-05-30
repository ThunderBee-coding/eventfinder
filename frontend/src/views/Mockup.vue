<script setup lang="ts">
import { ref, computed } from 'vue'

const activeTab = ref<'dashboard' | 'event' | 'login'>('dashboard')
const activeAccent = ref('#06b6d4')

const accents = [
  { label: 'Cyan', value: '#06b6d4' },
  { label: 'Violet', value: '#8b5cf6' },
  { label: 'Rose', value: '#f43f5e' },
  { label: 'Amber', value: '#f59e0b' },
  { label: 'Emerald', value: '#10b981' },
]

const mockEvents = [
  {
    id: 1, title: 'Sommerfest 🌞', desc: 'Grillabend bei Jonas',
    accent: '#f59e0b', cover: 'linear-gradient(135deg, #78350f, #92400e, #713f12)',
    participants: 8, dateRange: 'Jul 12–20', status: 'Abstimmung läuft'
  },
  {
    id: 2, title: 'Spieleabend 🎲', desc: 'Brettspiele und Pizza',
    accent: '#8b5cf6', cover: 'linear-gradient(135deg, #2e1065, #3b0764, #1e1b4b)',
    participants: 5, dateRange: 'Aug 3–10', status: 'Abstimmung läuft'
  },
  {
    id: 3, title: 'Konzert 🎸', desc: 'Radiohead @ Olympiastadion',
    accent: '#f43f5e', cover: 'linear-gradient(135deg, #4c0519, #881337, #3f0318)',
    participants: 12, dateRange: '15. Sep', status: 'Datum festgelegt'
  },
]

const glowStyle = computed(() => ({
  boxShadow: `0 0 40px ${activeAccent.value}33`
}))

const btnStyle = computed(() => ({
  background: activeAccent.value,
  boxShadow: `0 0 24px ${activeAccent.value}66`,
  color: '#000',
}))

const cardHover = (el: HTMLElement, accent: string, enter: boolean) => {
  el.style.boxShadow = enter ? `0 0 32px ${accent}44, inset 0 0 0 1px ${accent}33` : 'none'
  el.style.transform = enter ? 'scale(1.02)' : 'scale(1)'
}
</script>

<template>
  <div style="min-height:100vh; background:#080b14; color:#fff; font-family:system-ui,sans-serif;">

    <!-- TOP NAV -->
    <div style="position:sticky; top:0; z-index:50; background:rgba(8,11,20,0.85); backdrop-filter:blur(12px); border-bottom:1px solid rgba(255,255,255,0.06); padding:12px 24px; display:flex; align-items:center; justify-content:space-between;">
      <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-weight:700; font-size:18px; letter-spacing:-0.5px;">EventFinder</span>
        <span style="font-size:11px; color:rgba(255,255,255,0.3); background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:20px;">Mockup</span>
      </div>
      <div style="display:flex; gap:4px; background:rgba(255,255,255,0.05); border-radius:12px; padding:4px;">
        <button v-for="tab in ['dashboard','event','login']" :key="tab"
          @click="activeTab = tab as any"
          :style="{
            padding:'6px 16px', borderRadius:'8px', border:'none', cursor:'pointer', fontSize:'13px', fontWeight:500,
            background: activeTab === tab ? 'rgba(255,255,255,0.12)' : 'transparent',
            color: activeTab === tab ? '#fff' : 'rgba(255,255,255,0.4)',
            transition:'all .2s'
          }">
          {{ tab === 'dashboard' ? 'Dashboard' : tab === 'event' ? 'Event-Detail' : 'Login' }}
        </button>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:12px; color:rgba(255,255,255,0.3);">Akzent:</span>
        <button v-for="a in accents" :key="a.value"
          @click="activeAccent = a.value"
          :title="a.label"
          :style="{
            width:'20px', height:'20px', borderRadius:'50%', border:'none', cursor:'pointer',
            background: a.value,
            boxShadow: activeAccent === a.value ? `0 0 14px ${a.value}` : 'none',
            transform: activeAccent === a.value ? 'scale(1.3)' : 'scale(1)',
            transition:'all .2s', opacity: activeAccent === a.value ? 1 : 0.55
          }" />
      </div>
    </div>

    <!-- ======== DASHBOARD ======== -->
    <div v-if="activeTab === 'dashboard'" style="max-width:1000px; margin:0 auto; padding:40px 24px;">
      <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:36px;">
        <div>
          <p style="color:rgba(255,255,255,0.35); font-size:13px; margin-bottom:4px;">Willkommen zurück</p>
          <h1 style="font-size:30px; font-weight:700; letter-spacing:-0.5px; margin:0;">Meine Events</h1>
        </div>
        <button :style="{
          ...btnStyle,
          padding:'10px 20px', borderRadius:'12px', border:'none', cursor:'pointer',
          fontWeight:600, fontSize:'14px', display:'flex', alignItems:'center', gap:'6px'
        }">
          ＋ Neues Event
        </button>
      </div>

      <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:20px;">
        <div v-for="ev in mockEvents" :key="ev.id"
          style="border-radius:18px; overflow:hidden; background:#0d1117; border:1px solid rgba(255,255,255,0.07); cursor:pointer; transition:all .25s;"
          @mouseenter="e => cardHover(e.currentTarget as HTMLElement, ev.accent, true)"
          @mouseleave="e => cardHover(e.currentTarget as HTMLElement, ev.accent, false)">
          <!-- Cover -->
          <div :style="{ background: ev.cover, height:'110px', position:'relative' }">
            <div style="position:absolute; inset:0; background:rgba(0,0,0,0.15);" />
            <div :style="{
              position:'absolute', bottom:0, left:0, right:0, height:'1px',
              background:`linear-gradient(90deg, transparent, ${ev.accent}, transparent)`
            }" />
            <span :style="{
              position:'absolute', top:'12px', right:'12px', fontSize:'11px',
              padding:'3px 10px', borderRadius:'20px', background:'rgba(0,0,0,0.5)',
              backdropFilter:'blur(8px)', border:'1px solid rgba(255,255,255,0.1)',
              color: ev.accent
            }">{{ ev.status }}</span>
          </div>
          <!-- Body -->
          <div style="padding:18px;">
            <h2 style="font-size:17px; font-weight:600; margin:0 0 6px;">{{ ev.title }}</h2>
            <p style="color:rgba(255,255,255,0.4); font-size:13px; margin:0 0 16px;">{{ ev.desc }}</p>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:rgba(255,255,255,0.3);">
              <span>📅 {{ ev.dateRange }}</span>
              <span>👥 {{ ev.participants }}</span>
            </div>
          </div>
        </div>

        <!-- Add card -->
        <div style="border-radius:18px; border:1.5px dashed rgba(255,255,255,0.1); min-height:186px; display:flex; align-items:center; justify-content:center; cursor:pointer; transition:all .2s;"
          @mouseenter="e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.25)' }"
          @mouseleave="e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.1)' }">
          <div style="text-align:center;">
            <div style="font-size:28px; color:rgba(255,255,255,0.15); margin-bottom:8px;">＋</div>
            <p style="color:rgba(255,255,255,0.2); font-size:13px; margin:0;">Event erstellen</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== EVENT DETAIL ======== -->
    <div v-if="activeTab === 'event'" style="max-width:960px; margin:0 auto; padding:40px 24px;">
      <!-- Hero -->
      <div :style="{
        borderRadius:'20px', overflow:'hidden', marginBottom:'28px', height:'200px', position:'relative',
        background:`linear-gradient(135deg, #1a0a2e, #0d0a1e, #0a1a2e)`,
        boxShadow:`0 20px 60px ${activeAccent}33`
      }">
        <div :style="{ position:'absolute', inset:0, background:`radial-gradient(ellipse at 30% 60%, ${activeAccent}44 0%, transparent 65%)` }" />
        <div style="position:absolute; inset:0; padding:32px; display:flex; flex-direction:column; justify-content:flex-end;">
          <div style="display:flex; align-items:flex-end; justify-content:space-between;">
            <div>
              <p style="color:rgba(255,255,255,0.4); font-size:13px; margin:0 0 4px;">Konzertbesuch</p>
              <h1 style="font-size:28px; font-weight:700; letter-spacing:-0.5px; margin:0 0 10px;">Radiohead 🎸</h1>
              <div style="display:flex; gap:20px; font-size:13px; color:rgba(255,255,255,0.45);">
                <span>📍 Olympiastadion München</span>
                <span>👥 12 Teilnehmer</span>
              </div>
            </div>
            <button :style="{
              ...btnStyle,
              padding:'10px 18px', borderRadius:'12px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'13px'
            }">Teilnehmer einladen</button>
          </div>
        </div>
        <div :style="{
          position:'absolute', bottom:0, left:0, right:0, height:'1px',
          background:`linear-gradient(90deg, transparent, ${activeAccent}, transparent)`
        }" />
      </div>

      <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
        <!-- Left column -->
        <div style="display:flex; flex-direction:column; gap:16px;">
          <!-- Datumsvorschläge -->
          <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:20px;">
            <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin:0 0 14px;">Datumsvorschläge</p>
            <div v-for="(day, i) in ['15. Sep','16. Sep','22. Sep']" :key="i"
              style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-radius:10px; margin-bottom:6px; cursor:pointer; transition:all .15s;"
              :style="{ background: i===0 ? 'rgba(255,255,255,0.07)' : 'transparent', border: i===0 ? '1px solid rgba(255,255,255,0.1)' : '1px solid transparent' }">
              <span style="font-size:14px; font-weight:500;">{{ day }}</span>
              <div style="display:flex; gap:3px;">
                <span v-for="(s,j) in (i===0 ? ['🟢','🟢','🟡','🟢'] : i===1 ? ['🟢','🔴','🟢','🟡'] : ['🟡','🟢','🟢','🔴'])" :key="j" style="font-size:10px;">{{ s }}</span>
              </div>
            </div>
          </div>

          <!-- Teilnehmer -->
          <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:20px;">
            <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin:0 0 14px;">Teilnehmer</p>
            <div v-for="(p, i) in ['Jonas K.','Sarah M.','Tom B.','Lisa R.']" :key="i"
              style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.04);">
              <div style="display:flex; align-items:center; gap:10px;">
                <div :style="{
                  width:'30px', height:'30px', borderRadius:'50%', display:'flex',
                  alignItems:'center', justifyContent:'center', fontSize:'12px', fontWeight:700,
                  background: activeAccent, color:'#000'
                }">{{ p[0] }}</div>
                <span style="font-size:14px;">{{ p }}</span>
              </div>
              <span :style="{ fontSize:'11px', color: i < 3 ? '#10b981' : '#f59e0b' }">
                {{ i < 3 ? 'Abgestimmt' : 'Ausstehend' }}
              </span>
            </div>
            <button style="margin-top:14px; width:100%; padding:9px; border-radius:10px; background:transparent; border:1.5px dashed rgba(255,255,255,0.12); color:rgba(255,255,255,0.3); font-size:13px; cursor:pointer; transition:all .2s;">
              + Teilnehmer einladen
            </button>
          </div>
        </div>

        <!-- Calendar -->
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:16px; padding:24px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin:0 0 16px;">Verfügbarkeitskalender</p>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <span style="font-weight:600; font-size:16px;">September 2026</span>
            <div>
              <button style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:28px; height:28px; border-radius:8px; cursor:pointer; margin-right:4px;">‹</button>
              <button style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:28px; height:28px; border-radius:8px; cursor:pointer;">›</button>
            </div>
          </div>
          <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px; text-align:center; margin-bottom:8px;">
            <span v-for="d in ['Mo','Di','Mi','Do','Fr','Sa','So']" :key="d" style="font-size:11px; color:rgba(255,255,255,0.3); padding:4px 0;">{{ d }}</span>
          </div>
          <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px; text-align:center;">
            <div v-for="i in 2" :key="'e'+i" />
            <div v-for="day in 30" :key="day"
              style="height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:13px; cursor:pointer; transition:all .15s;"
              :style="{
                background: day===15 ? activeAccent : day===16 ? 'rgba(244,63,94,0.2)' : day===22 ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.02)',
                color: day===15 ? '#000' : day===16 ? '#f43f5e' : day===22 ? '#f59e0b' : 'rgba(255,255,255,0.45)',
                fontWeight: day===15 ? 700 : 400,
                boxShadow: day===15 ? `0 0 14px ${activeAccent}99` : 'none',
              }">
              {{ day }}
            </div>
          </div>
          <div style="display:flex; gap:20px; margin-top:18px;">
            <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
              <span style="width:10px; height:10px; border-radius:50%; background:#10b981; display:inline-block;"/> Sehr gut
            </span>
            <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
              <span style="width:10px; height:10px; border-radius:50%; background:#f59e0b; display:inline-block;"/> Möglich
            </span>
            <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
              <span style="width:10px; height:10px; border-radius:50%; background:#f43f5e; display:inline-block;"/> Nicht möglich
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== LOGIN ======== -->
    <div v-if="activeTab === 'login'" style="min-height:calc(100vh - 57px); display:flex; align-items:center; justify-content:center; padding:24px; position:relative; overflow:hidden;">
      <!-- Glow bg -->
      <div :style="{
        position:'absolute', width:'500px', height:'500px', borderRadius:'50%',
        background: activeAccent, opacity:0.06, filter:'blur(80px)',
        pointerEvents:'none'
      }" />
      <div :style="{
        position:'relative', width:'100%', maxWidth:'380px',
        background:'rgba(255,255,255,0.04)', backdropFilter:'blur(20px)',
        borderRadius:'24px', padding:'40px', border:'1px solid rgba(255,255,255,0.09)',
        boxShadow:`0 0 60px ${activeAccent}22`
      }">
        <div style="text-align:center; margin-bottom:32px;">
          <div style="font-size:40px; margin-bottom:12px;">🗓️</div>
          <h1 style="font-size:24px; font-weight:700; letter-spacing:-0.5px; margin:0 0 6px;">EventFinder</h1>
          <p style="color:rgba(255,255,255,0.35); font-size:14px; margin:0;">Plane gemeinsame Events mit deinen Freunden</p>
        </div>
        <label style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px;">E-Mail Adresse</label>
        <input type="email" placeholder="du@beispiel.de"
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:12px; padding:12px 16px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; margin-bottom:16px;" />
        <button :style="{
          ...btnStyle,
          width:'100%', padding:'13px', borderRadius:'12px', border:'none',
          cursor:'pointer', fontWeight:600, fontSize:'14px'
        }">
          Magic Link anfordern ✉️
        </button>
        <p style="text-align:center; color:rgba(255,255,255,0.2); font-size:12px; margin:20px 0 0;">Kein Passwort nötig — du bekommst einen Link per E-Mail.</p>
      </div>
    </div>

  </div>
</template>
