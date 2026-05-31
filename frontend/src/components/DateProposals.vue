<script setup lang="ts">
const props = defineProps<{
  proposals: Array<{ id: string; proposed_date: string }>
  availabilities: Array<{ event_date: string; status: string; participant_name?: string; own?: boolean }>
  participants: Array<{ id: string; name: string }>
  participantCount: number
  accentColor: string
  finalDate?: string
  isOrganizer?: boolean
  holidays?: Record<string, string>
}>()

const emit = defineEmits<{ setFinal: [date: string] }>()

const _today = new Date()
_today.setHours(0, 0, 0, 0)

function isPast(isoDate: string) {
  return new Date(isoDate + 'T00:00:00') < _today
}

function formatDate(iso: string) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
  })
}

function votesForDate(date: string) {
  const dayAvails = props.availabilities.filter(a => a.event_date === date)
  const votedNames = new Set(dayAvails.map(a => a.participant_name).filter(Boolean))
  const pending = props.participants.filter(p => !votedNames.has(p.name))
  return {
    best: dayAvails.filter(a => a.status === 'best'),
    possible: dayAvails.filter(a => a.status === 'possible'),
    impossible: dayAvails.filter(a => a.status === 'impossible'),
    pending,
    total: props.participantCount,
  }
}

function barWidthPct(count: number, total: number) {
  return total > 0 ? Math.round((count / total) * 100) : 0
}
</script>

<template>
  <div>
    <!-- Legende -->
    <div style="display:flex; gap:10px; margin-bottom:12px; flex-wrap:wrap;">
      <span style="display:flex;align-items:center;gap:4px;font-size:10px;color:rgba(255,255,255,0.3);">
        <span style="width:8px;height:8px;border-radius:50%;background:#10b981;display:inline-block;"></span>Sehr gut
      </span>
      <span style="display:flex;align-items:center;gap:4px;font-size:10px;color:rgba(255,255,255,0.3);">
        <span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>Möglich
      </span>
      <span style="display:flex;align-items:center;gap:4px;font-size:10px;color:rgba(255,255,255,0.3);">
        <span style="width:8px;height:8px;border-radius:50%;background:#f43f5e;display:inline-block;"></span>Nicht möglich
      </span>
    </div>

    <div v-if="proposals.length === 0" style="color:rgba(255,255,255,0.25); font-size:13px;">Noch keine Vorschläge.</div>

    <div v-for="p in proposals" :key="p.id"
      :style="{
        padding: '10px 0',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        position: 'relative',
        opacity: isPast(p.proposed_date) ? 0.45 : 1,
      }">

      <!-- Datum-Header -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <span :style="{
            fontSize: '13px', fontWeight: 600,
            textDecoration: isPast(p.proposed_date) ? 'line-through' : 'none',
            color: isPast(p.proposed_date) ? 'rgba(255,255,255,0.3)' : '#fff'
          }">{{ formatDate(p.proposed_date) }}</span>

          <span v-if="isPast(p.proposed_date)"
            style="font-size:10px; color:#f43f5e; background:rgba(244,63,94,0.1); border:1px solid rgba(244,63,94,0.2); border-radius:4px; padding:1px 6px;">
            Vergangenheit
          </span>
          <span v-else-if="holidays?.[p.proposed_date]"
            style="font-size:10px; color:#f97316; background:rgba(249,115,22,0.1); border:1px solid rgba(249,115,22,0.25); border-radius:4px; padding:1px 6px;">
            🎉 {{ holidays[p.proposed_date] }}
          </span>
          <span v-if="finalDate === p.proposed_date"
            :style="{ fontSize:'11px', color: accentColor, fontWeight:600 }">✓ Finaldatum</span>
        </div>
        <button v-if="isOrganizer && finalDate !== p.proposed_date && !isPast(p.proposed_date)"
          @click="emit('setFinal', p.proposed_date)"
          style="font-size:11px; color:rgba(255,255,255,0.35); background:transparent; border:1px solid rgba(255,255,255,0.1); padding:3px 8px; border-radius:6px; cursor:pointer; flex-shrink:0;">
          Als Final setzen
        </button>
      </div>

      <!-- Abstimmungsbalken + Zähler (nur für zukünftige Termine) -->
      <template v-if="!isPast(p.proposed_date)">
        <div style="display:flex; height:6px; border-radius:3px; overflow:hidden; gap:1px; margin-bottom:6px; background:rgba(255,255,255,0.06);">
          <div :style="{ width: barWidthPct(votesForDate(p.proposed_date).best.length, participantCount) + '%', background: '#10b981', borderRadius:'2px', transition:'width .3s' }" />
          <div :style="{ width: barWidthPct(votesForDate(p.proposed_date).possible.length, participantCount) + '%', background: '#f59e0b', borderRadius:'2px', transition:'width .3s' }" />
          <div :style="{ width: barWidthPct(votesForDate(p.proposed_date).impossible.length, participantCount) + '%', background: '#f43f5e', borderRadius:'2px', transition:'width .3s' }" />
        </div>

        <div style="display:flex; gap:10px; font-size:11px; flex-wrap:wrap;">
          <span v-if="votesForDate(p.proposed_date).best.length > 0" style="display:flex;align-items:center;gap:3px;color:#10b981;">
            <span style="width:6px;height:6px;border-radius:50%;background:#10b981;display:inline-block;"></span>
            {{ votesForDate(p.proposed_date).best.length }} sehr gut
          </span>
          <span v-if="votesForDate(p.proposed_date).possible.length > 0" style="display:flex;align-items:center;gap:3px;color:#f59e0b;">
            <span style="width:6px;height:6px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>
            {{ votesForDate(p.proposed_date).possible.length }} möglich
          </span>
          <span v-if="votesForDate(p.proposed_date).impossible.length > 0" style="display:flex;align-items:center;gap:3px;color:#f43f5e;">
            <span style="width:6px;height:6px;border-radius:50%;background:#f43f5e;display:inline-block;"></span>
            {{ votesForDate(p.proposed_date).impossible.length }} nicht möglich
          </span>
          <span v-if="votesForDate(p.proposed_date).pending.length > 0" style="display:flex;align-items:center;gap:3px;color:rgba(255,255,255,0.3);">
            <span style="width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.15);display:inline-block;"></span>
            {{ votesForDate(p.proposed_date).pending.length }} offen
          </span>
        </div>

        <!-- Hover-Tooltip mit Namen -->
        <div class="vote-names-tooltip">
          <p style="font-size:10px; color:rgba(255,255,255,0.3); text-transform:uppercase; letter-spacing:.06em; margin:0 0 8px;">Wer hat wie abgestimmt</p>
          <div v-for="v in votesForDate(p.proposed_date).best" :key="'b-'+v.participant_name"
            style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px;">
            <span style="color:rgba(255,255,255,0.8);">{{ v.participant_name }}</span>
            <span style="font-size:11px;font-weight:600;padding:1px 7px;border-radius:4px;background:rgba(16,185,129,0.15);color:#10b981;">Sehr gut</span>
          </div>
          <div v-for="v in votesForDate(p.proposed_date).possible" :key="'p-'+v.participant_name"
            style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px;">
            <span style="color:rgba(255,255,255,0.8);">{{ v.participant_name }}</span>
            <span style="font-size:11px;font-weight:600;padding:1px 7px;border-radius:4px;background:rgba(245,158,11,0.15);color:#f59e0b;">Möglich</span>
          </div>
          <div v-for="v in votesForDate(p.proposed_date).impossible" :key="'i-'+v.participant_name"
            style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px;">
            <span style="color:rgba(255,255,255,0.8);">{{ v.participant_name }}</span>
            <span style="font-size:11px;font-weight:600;padding:1px 7px;border-radius:4px;background:rgba(244,63,94,0.15);color:#f43f5e;">Nicht möglich</span>
          </div>
          <div v-for="u in votesForDate(p.proposed_date).pending" :key="'x-'+u.id"
            style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px;opacity:0.45;">
            <span style="color:rgba(255,255,255,0.6);">⏳ {{ u.name }}</span>
            <span style="font-size:11px;color:rgba(255,255,255,0.3);">ausstehend</span>
          </div>
        </div>
      </template>

      <div v-else style="font-size:11px; color:rgba(255,255,255,0.2); margin-top:4px;">
        Automatisch als nicht möglich markiert
      </div>
    </div>
  </div>
</template>

<style scoped>
.vote-names-tooltip {
  display: none;
  position: absolute;
  left: 0;
  bottom: 100%;
  margin-bottom: 4px;
  background: #1a2035;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 10px 14px;
  width: 260px;
  z-index: 200;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  pointer-events: none;
}
div:hover > .vote-names-tooltip {
  display: block;
}
</style>
