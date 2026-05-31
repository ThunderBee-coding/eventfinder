<script setup lang="ts">
defineProps<{
  participants: Array<{ id: string; name: string; email: string; joined_at: string; availability_count: number }>
  accentColor: string
  totalProposals: number
  isOrganizer?: boolean
  organizerId?: string
  myUserId?: string
}>()

const emit = defineEmits<{
  invite: []
  delete: [id: string]
  transferOrganizer: [id: string]
}>()

function initials(name: string) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
</script>

<template>
  <div>
    <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">Teilnehmer ({{ participants.length }})</p>
    <div v-for="p in participants" :key="p.id"
      style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
      <div style="display:flex; align-items:center; gap:10px;">
        <div :style="{ width:'32px', height:'32px', borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'12px', fontWeight:700, background: p.id === organizerId ? accentColor : 'rgba(255,255,255,0.12)', color: p.id === organizerId ? '#000' : '#fff', flexShrink:0 }">
          {{ initials(p.name) }}
        </div>
        <div>
          <div style="display:flex; align-items:center; gap:6px;">
            <p style="font-size:14px; font-weight:500; margin-bottom:1px;">{{ p.name }}</p>
            <span v-if="p.id === organizerId" :style="{ fontSize:'10px', color: accentColor, fontWeight:700, letterSpacing:'0.05em' }">ORG</span>
          </div>
          <p style="font-size:11px; color:rgba(255,255,255,0.3);">{{ p.email }}</p>
        </div>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span :style="{ fontSize:'12px', color: p.availability_count >= totalProposals && totalProposals > 0 ? '#10b981' : p.availability_count > 0 ? '#f59e0b' : 'rgba(255,255,255,0.3)' }">
          {{ p.availability_count >= totalProposals && totalProposals > 0 ? 'Vollständig' : p.availability_count > 0 ? `${p.availability_count}/${totalProposals}` : 'Ausstehend' }}
        </span>
        <template v-if="isOrganizer && p.id !== myUserId">
          <button
            v-if="p.id !== organizerId"
            @click="emit('transferOrganizer', p.id)"
            title="Zum Organisator machen"
            style="background:transparent; border:1px solid rgba(255,255,255,0.1); border-radius:6px; color:rgba(255,255,255,0.4); cursor:pointer; padding:3px 7px; font-size:13px; line-height:1;"
          >👑</button>
          <button
            @click="emit('delete', p.id)"
            title="Teilnehmer entfernen"
            style="background:transparent; border:1px solid rgba(244,63,94,0.25); border-radius:6px; color:rgba(244,63,94,0.6); cursor:pointer; padding:3px 7px; font-size:13px; line-height:1;"
          >×</button>
        </template>
      </div>
    </div>
    <button v-if="isOrganizer" @click="emit('invite')"
      style="margin-top:14px; width:100%; padding:9px; border-radius:10px; background:transparent; border:1.5px dashed rgba(255,255,255,0.12); color:rgba(255,255,255,0.35); font-size:13px; cursor:pointer; transition:all .2s;"
      @mouseenter="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.3)'; (e.currentTarget as HTMLElement).style.color='rgba(255,255,255,0.6)' }"
      @mouseleave="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.12)'; (e.currentTarget as HTMLElement).style.color='rgba(255,255,255,0.35)' }">
      + Teilnehmer einladen
    </button>
  </div>
</template>
