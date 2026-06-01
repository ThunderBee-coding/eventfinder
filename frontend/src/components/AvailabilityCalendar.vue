<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  proposedDates: string[]
  availabilities: Array<{ event_date: string; status: 'best' | 'possible' | 'impossible'; own?: boolean }>
  participantCount: number
  accentColor: string
  finalDate?: string
  holidays?: Record<string, string>
  weatherHints?: Record<string, {
    temp_max_median: number | null
    temp_min_median: number | null
    precip_median: number | null
    loading: boolean
    forecast_temp_max: number | null
    forecast_temp_min: number | null
    forecast_code: number | null
  }>
}>()

const emit = defineEmits<{ dateClick: [date: string] }>()

const _firstDate = props.proposedDates.length > 0
  ? new Date(props.proposedDates[0] + 'T00:00:00')
  : new Date()
const currentYear = ref(_firstDate.getFullYear())
const currentMonth = ref(_firstDate.getMonth())

const monthName = computed(() =>
  new Date(currentYear.value, currentMonth.value).toLocaleString('de-DE', { month: 'long', year: 'numeric' })
)
const daysInMonth = computed(() => new Date(currentYear.value, currentMonth.value + 1, 0).getDate())
const firstDayOffset = computed(() => {
  const d = new Date(currentYear.value, currentMonth.value, 1).getDay()
  return d === 0 ? 6 : d - 1
})

function isoDate(day: number) {
  const m = String(currentMonth.value + 1).padStart(2, '0')
  const d = String(day).padStart(2, '0')
  return `${currentYear.value}-${m}-${d}`
}

function isProposed(day: number) { return props.proposedDates.includes(isoDate(day)) }

function scoreForDay(day: number): 'best' | 'possible' | 'impossible' | null {
  const iso = isoDate(day)
  const avails = props.availabilities.filter(a => a.event_date === iso)
  if (avails.length === 0) return null
  const bestCount = avails.filter(a => a.status === 'best').length
  const impossibleCount = avails.filter(a => a.status === 'impossible').length
  if (impossibleCount > props.participantCount / 2) return 'impossible'
  if (bestCount >= props.participantCount / 2) return 'best'
  return 'possible'
}

function ownStatusForDay(day: number) {
  return props.availabilities.find(a => a.event_date === isoDate(day) && a.own)?.status
}

const _today = new Date()
_today.setHours(0, 0, 0, 0)

function isPast(day: number) {
  return new Date(isoDate(day) + 'T00:00:00') < _today
}

function dayBg(day: number) {
  const iso = isoDate(day)
  if (props.finalDate === iso) return props.accentColor
  if (!isProposed(day)) return 'transparent'
  const score = scoreForDay(day)
  if (score === 'best') return 'rgba(16,185,129,0.2)'
  if (score === 'possible') return 'rgba(245,158,11,0.18)'
  if (score === 'impossible') return 'rgba(244,63,94,0.18)'
  return 'rgba(255,255,255,0.05)'
}

function dayColor(day: number) {
  const iso = isoDate(day)
  if (props.finalDate === iso) return '#000'
  if (!isProposed(day)) return 'rgba(255,255,255,0.2)'
  const score = scoreForDay(day)
  if (score === 'best') return '#10b981'
  if (score === 'possible') return '#f59e0b'
  if (score === 'impossible') return '#f43f5e'
  return 'rgba(255,255,255,0.5)'
}

function prevMonth() {
  if (currentMonth.value === 0) { currentMonth.value = 11; currentYear.value-- }
  else currentMonth.value--
}
function nextMonth() {
  if (currentMonth.value === 11) { currentMonth.value = 0; currentYear.value++ }
  else currentMonth.value++
}

function isHoliday(day: number) {
  return !!(props.holidays?.[isoDate(day)])
}
function holidayName(day: number) {
  return props.holidays?.[isoDate(day)] || ''
}
function weatherHint(day: number) {
  return props.weatherHints?.[isoDate(day)] || null
}
function weatherCodeIcon(code: number | null): string {
  if (code === null) return ''
  if (code === 0) return '☀️'
  if (code <= 2) return '🌤'
  if (code <= 49) return '🌫'
  if (code <= 67) return '🌧'
  if (code <= 77) return '❄️'
  if (code <= 82) return '🌦'
  return '⛈'
}
</script>

<template>
  <div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
      <span style="font-weight:600; font-size:16px; text-transform:capitalize;">{{ monthName }}</span>
      <div>
        <button @click="prevMonth" style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:30px; height:30px; border-radius:8px; cursor:pointer; font-size:16px; margin-right:4px;">‹</button>
        <button @click="nextMonth" style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:30px; height:30px; border-radius:8px; cursor:pointer; font-size:16px;">›</button>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-bottom:6px;">
      <span v-for="d in ['Mo','Di','Mi','Do','Fr','Sa','So']" :key="d" style="text-align:center; font-size:11px; color:rgba(255,255,255,0.3); padding:4px 0;">{{ d }}</span>
    </div>
    <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px;">
      <div v-for="i in firstDayOffset" :key="'e'+i" />
      <div v-for="day in daysInMonth" :key="day"
        :style="{
          height: '52px',
          borderRadius: '8px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '13px',
          fontWeight: isProposed(day) ? 600 : 400,
          position: 'relative',
          background: dayBg(day),
          color: dayColor(day),
          cursor: isProposed(day) && !isPast(day) ? 'pointer' : 'default',
          opacity: isPast(day) && isProposed(day) ? 0.35 : 1,
          boxShadow: finalDate === isoDate(day) ? `0 0 14px ${accentColor}99` : 'none',
          border: ownStatusForDay(day) ? `1px solid ${accentColor}66` : '1px solid transparent',
          transition: 'all .15s',
        }"
        @click="isProposed(day) && !isPast(day) && emit('dateClick', isoDate(day))">

        <!-- Feiertag-Punkt -->
        <div v-if="isHoliday(day)"
          style="position:absolute; top:4px; right:4px; width:5px; height:5px; border-radius:50%; background:#f97316;" />

        <span style="line-height:1;">{{ day }}</span>

        <!-- Wetter-Badge -->
        <span v-if="isProposed(day) && weatherHint(day) && !weatherHint(day)!.loading && weatherHint(day)!.temp_max_median !== null"
          style="font-size:9px; color:rgba(255,255,255,0.4); line-height:1; margin-top:1px; white-space:nowrap;">
          {{ Math.round(weatherHint(day)!.temp_max_median!) }}°/{{ Math.round(weatherHint(day)!.temp_min_median!) }}°
        </span>
        <span v-else-if="isProposed(day) && weatherHint(day)?.loading"
          style="font-size:9px; color:rgba(255,255,255,0.2); line-height:1; margin-top:1px;">⏳</span>

        <!-- Wetter-Tooltip (CSS :hover) -->
        <div v-if="isProposed(day)" class="weather-cal-tooltip">
          <template v-if="weatherHint(day)?.loading">
            <p style="font-size:11px; color:rgba(255,255,255,0.4); text-align:center; margin:0;">Wetterdaten laden…</p>
          </template>
          <template v-else-if="weatherHint(day) != null && weatherHint(day)!.temp_max_median != null">
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
              <span style="color:rgba(255,255,255,0.5);">🌡 Ø Hoch</span>
              <b>{{ Math.round(weatherHint(day)!.temp_max_median!) }}°C</b>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
              <span style="color:rgba(255,255,255,0.5);">🌡 Ø Tief</span>
              <b>{{ Math.round(weatherHint(day)!.temp_min_median!) }}°C</b>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:5px;">
              <span style="color:rgba(255,255,255,0.5);">🌧 Regen Ø</span>
              <b>{{ weatherHint(day)!.precip_median?.toFixed(1) ?? '—' }} mm</b>
            </div>
            <p style="font-size:10px; color:rgba(255,255,255,0.25); text-align:center; margin:0 0 4px;">Klimamittel 2005–2024</p>
            <div v-if="weatherHint(day)!.forecast_temp_max !== null"
              style="background:rgba(6,182,212,0.12); border:1px solid rgba(6,182,212,0.25); border-radius:6px; padding:4px 8px; text-align:center; font-size:11px; color:#06b6d4;">
              📡 {{ weatherCodeIcon(weatherHint(day)!.forecast_code) }} {{ Math.round(weatherHint(day)!.forecast_temp_max!) }}°C
            </div>
          </template>
          <p v-if="isHoliday(day)"
            style="font-size:11px; color:#f97316; text-align:center; margin:5px 0 0;">
            🎉 {{ holidayName(day) }}
          </p>
        </div>
      </div>
    </div>
    <div style="display:flex; gap:16px; margin-top:16px; flex-wrap:wrap;">
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);"><span style="width:10px;height:10px;border-radius:50%;background:#10b981;display:inline-block"/>Mehrheit: gut</span>
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);"><span style="width:10px;height:10px;border-radius:50%;background:#f59e0b;display:inline-block"/>Möglich</span>
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);"><span style="width:10px;height:10px;border-radius:50%;background:#f43f5e;display:inline-block"/>Nicht möglich</span>
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
        <span style="width:6px;height:6px;border-radius:50%;background:#f97316;display:inline-block;"></span>Feiertag
      </span>
    </div>
  </div>
</template>

<style scoped>
.weather-cal-tooltip {
  display: none;
  position: absolute;
  bottom: 110%;
  left: 50%;
  transform: translateX(-50%);
  background: #1a2035;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 10px 12px;
  width: 180px;
  z-index: 300;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  pointer-events: none;
  white-space: normal;
}
div:hover > .weather-cal-tooltip {
  display: block;
}
</style>
