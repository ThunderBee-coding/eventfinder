<script setup lang="ts">
defineProps<{
  proposals: Array<{ id: string; proposed_date: string }>
  availabilities: Array<{ event_date: string; status: string }>
  participantCount: number
  accentColor: string
  finalDate?: string
  isOrganizer?: boolean
}>()

const emit = defineEmits<{ setFinal: [date: string] }>()

function scoreColor(date: string, avails: Array<{event_date:string; status:string}>, total: number) {
  const dayAvails = avails.filter(a => a.event_date === date)
  const best = dayAvails.filter(a => a.status === 'best').length
  const impossible = dayAvails.filter(a => a.status === 'impossible').length
  if (impossible > total / 2) return '#f43f5e'
  if (best >= total / 2) return '#10b981'
  if (dayAvails.length > 0) return '#f59e0b'
  return 'rgba(255,255,255,0.2)'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' })
}
</script>

<template>
  <div>
    <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">Datumsvorschläge</p>
    <div v-if="proposals.length === 0" style="color:rgba(255,255,255,0.25); font-size:13px;">Noch keine Vorschläge.</div>
    <div v-for="p in proposals" :key="p.id"
      style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-radius:10px; margin-bottom:6px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.07);">
      <div style="display:flex; align-items:center; gap:10px;">
        <span :style="{ width:'10px', height:'10px', borderRadius:'50%', background: scoreColor(p.proposed_date, availabilities, participantCount), display:'inline-block', flexShrink:0 }" />
        <span style="font-size:14px; font-weight:500;">{{ formatDate(p.proposed_date) }}</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span v-if="finalDate === p.proposed_date" :style="{ fontSize:'11px', color: accentColor, fontWeight:600 }">✓ Finaldatum</span>
        <button v-else-if="isOrganizer" @click="emit('setFinal', p.proposed_date)"
          style="font-size:11px; color:rgba(255,255,255,0.35); background:transparent; border:1px solid rgba(255,255,255,0.1); padding:3px 8px; border-radius:6px; cursor:pointer;">
          Als Final setzen
        </button>
      </div>
    </div>
  </div>
</template>
