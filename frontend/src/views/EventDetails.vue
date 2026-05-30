<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import Calendar from '../components/Calendar.vue'
import { MapPin, Info, Cloud } from '@lucide/vue'

const route = useRoute()
const event = ref<any>(null)
const availabilities = ref<any[]>([])
const loading = ref(true)
const selectedDate = ref('')
const showAvailabilityModal = ref(false)
const availabilityStatus = ref('possible')
const comment = ref('')

const fetchEventData = async () => {
  try {
    const token = localStorage.getItem('token')
    const eventId = route.params.id
    const [eventRes, availRes] = await Promise.all([
      axios.get(`/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      }),
      axios.get(`/events/${eventId}/availability`, {
        headers: { Authorization: `Bearer ${token}` }
      })
    ])
    event.value = eventRes.data
    availabilities.value = availRes.data
  } catch (err) {
    console.error('Error fetching event details:', err)
  } finally {
    loading.value = false
  }
}

const onDateClick = (dateStr: string) => {
  selectedDate.value = dateStr
  const existing = availabilities.value.find(a => a.event_date === dateStr)
  if (existing) {
    availabilityStatus.value = existing.status
    comment.value = existing.comment || ''
  } else {
    availabilityStatus.value = 'possible'
    comment.value = ''
  }
  showAvailabilityModal.value = true
}

const saveAvailability = async () => {
  try {
    const token = localStorage.getItem('token')
    await axios.post(`/events/${event.value.id}/availability`, {
      event_date: selectedDate.value,
      status: availabilityStatus.value,
      comment: comment.value
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    showAvailabilityModal.value = false
    fetchEventData()
  } catch (err) {
    console.error('Error saving availability:', err)
  }
}

const calendarEvents = computed(() => {
  return availabilities.value.map(a => ({
    title: a.status === 'best' ? 'Favorit' : a.status === 'possible' ? 'Vielleicht' : 'Nicht möglich',
    start: a.event_date,
    color: a.status === 'best' ? '#10b981' : a.status === 'possible' ? '#f59e0b' : '#ef4444',
    allDay: true
  }))
})

onMounted(fetchEventData)
</script>

<template>
  <div v-if="loading" class="flex items-center justify-center min-h-screen">
    <p class="text-gray-500">Lade Event-Details...</p>
  </div>

  <div v-else-if="event" class="max-w-6xl mx-auto p-8">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Left side: Info -->
      <div class="lg:col-span-1 space-y-6">
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h1 class="text-2xl font-bold text-gray-900 mb-4">{{ event.title }}</h1>
          <p class="text-gray-600 mb-6">{{ event.description }}</p>
          
          <div class="space-y-4">
            <div class="flex items-start gap-3 text-sm">
              <MapPin class="text-gray-400 mt-1" size="18" />
              <div>
                <p class="font-medium">Ort</p>
                <p class="text-gray-500">{{ event.location_name || 'Noch nicht festgelegt' }}</p>
              </div>
            </div>
            
            <div class="flex items-start gap-3 text-sm">
              <Info class="text-gray-400 mt-1" size="18" />
              <div>
                <p class="font-medium">Status</p>
                <p class="text-gray-500">{{ event.is_closed ? 'Abgeschlossen' : 'Terminfindung läuft' }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Weather Placeholder -->
        <div class="bg-blue-50 p-6 rounded-xl border border-blue-100">
          <div class="flex items-center gap-2 text-blue-800 font-semibold mb-2">
            <Cloud size="20" />
            Wettervorhersage
          </div>
          <p class="text-sm text-blue-600">
            Wähle einen Termin aus, um die Wettervorhersage für diesen Tag zu sehen.
          </p>
        </div>
      </div>

      <!-- Right side: Calendar -->
      <div class="lg:col-span-2">
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h2 class="text-xl font-semibold mb-4 text-gray-900">Deine Verfügbarkeit</h2>
          <p class="text-sm text-gray-500 mb-6">Klicke auf einen Tag im Kalender, um deine Verfügbarkeit anzugeben.</p>
          <Calendar :events="calendarEvents" @dateClick="onDateClick" />
        </div>
      </div>
    </div>

    <!-- Availability Modal -->
    <div v-if="showAvailabilityModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-8 max-w-md w-full">
        <h2 class="text-2xl font-bold mb-2">Verfügbarkeit am {{ selectedDate }}</h2>
        <p class="text-gray-500 mb-6">Wie sieht es an diesem Tag bei dir aus?</p>
        
        <div class="space-y-4">
          <div class="flex flex-col gap-2">
            <label class="text-sm font-medium text-gray-700">Status</label>
            <select v-model="availabilityStatus" class="w-full px-3 py-2 border border-gray-300 rounded-lg">
              <option value="best">Sehr gut (Favorit)</option>
              <option value="possible">Möglich</option>
              <option value="impossible">Nicht möglich</option>
            </select>
          </div>
          
          <div class="flex flex-col gap-2">
            <label class="text-sm font-medium text-gray-700">Kommentar (optional)</label>
            <input v-model="comment" type="text" placeholder="z.B. erst ab 18 Uhr"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg">
          </div>
        </div>
        
        <div class="flex justify-end gap-3 mt-8">
          <button @click="showAvailabilityModal = false" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
            Abbrechen
          </button>
          <button @click="saveAvailability"
            class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            Speichern
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
