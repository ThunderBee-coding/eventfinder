<script setup lang="ts">
import { ref, onMounted } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'

const props = defineProps<{
  events?: any[]
}>()

const emit = defineEmits(['dateClick'])

const calendarOptions = ref({
  plugins: [dayGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  locale: 'de',
  firstDay: 1,
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: ''
  },
  dateClick: (info: any) => {
    emit('dateClick', info.dateStr)
  },
  events: props.events || []
})
</script>

<template>
  <div class="calendar-container bg-white p-4 rounded-lg shadow">
    <FullCalendar :options="calendarOptions" />
  </div>
</template>

<style>
.fc {
  max-width: 100%;
}
.fc-day-sun, .fc-day-sat {
  background-color: #f9fafb;
}
</style>
