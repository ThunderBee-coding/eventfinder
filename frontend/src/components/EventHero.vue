<script setup lang="ts">
const props = defineProps<{
  title: string
  description?: string
  locationName?: string
  address?: string
  accentColor: string
  coverImagePath?: string
  participantCount?: number
  isOrganizer?: boolean
}>()

const emit = defineEmits<{
  invite: []
  editCover: []
  editLocation: []
  updateLocation: [value: string]
}>()
</script>

<template>
  <div :style="{
    position: 'relative', borderRadius: '20px', overflow: 'hidden', height: '220px',
    boxShadow: `0 20px 60px ${accentColor}33`,
  }">
    <img v-if="coverImagePath" :src="`/${coverImagePath}`"
      style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;" />
    <div v-else :style="{
      position: 'absolute', inset: 0,
      background: `linear-gradient(135deg, ${accentColor}22 0%, #080b14 100%)`,
    }" />
    <div style="position:absolute; inset:0; background:linear-gradient(to top, rgba(8,11,20,0.95) 0%, rgba(8,11,20,0.4) 100%);" />
    <div :style="{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px',
      background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
    }" />
    <div style="position:absolute; inset:0; padding:28px 32px; display:flex; flex-direction:column; justify-content:flex-end;">
      <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:16px;">
        <div style="flex:1; min-width:0;">
          <!-- Ort: Anzeige + Edit-Button (Edit-State liegt in EventDetails) -->
          <div style="display:flex; align-items:center; gap:6px; margin-bottom:6px; min-height:22px;">
            <p v-if="address || locationName" style="font-size:13px; color:rgba(255,255,255,0.45); margin:0;">
              📍 {{ address || locationName }}
            </p>
            <button
              v-if="isOrganizer"
              @click="emit('editLocation')"
              style="background:transparent; border:1px solid rgba(255,255,255,0.15); border-radius:5px; color:rgba(255,255,255,0.35); font-size:11px; cursor:pointer; padding:2px 7px; line-height:1.4;"
            >{{ (address || locationName) ? '✏ Ort ändern' : '+ Ort hinzufügen' }}</button>
          </div>
          <h1 style="font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:8px; line-height:1.2;">{{ title }}</h1>
          <p v-if="description" style="font-size:14px; color:rgba(255,255,255,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{{ description }}</p>
          <p v-if="participantCount !== undefined" style="font-size:13px; color:rgba(255,255,255,0.35); margin-top:8px;">👥 {{ participantCount }} Teilnehmer</p>
        </div>
        <div v-if="isOrganizer" style="display:flex; flex-direction:column; gap:8px; flex-shrink:0;">
          <button @click="emit('invite')" :style="{
            background: accentColor, boxShadow: `0 0 20px ${accentColor}66`, color: '#000',
            padding: '9px 16px', borderRadius: '10px', border: 'none', cursor: 'pointer',
            fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap',
          }">+ Einladen</button>
          <button @click="emit('editCover')" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.7); padding:9px 16px; border-radius:10px; cursor:pointer; font-size:13px; font-weight:500;">🖼 Cover</button>
        </div>
      </div>
    </div>
  </div>
</template>
