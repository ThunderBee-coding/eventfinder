<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Plus, Calendar as CalendarIcon } from '@lucide/vue'

const events = ref([])
const loading = ref(true)
const showCreateModal = ref(false)
const newEvent = ref({
  title: '',
  description: ''
})

const fetchEvents = async () => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('/events/', {
      headers: { Authorization: `Bearer ${token}` }
    })
    events.value = response.data
  } catch (err) {
    console.error('Error fetching events:', err)
  } finally {
    loading.value = false
  }
}

const createEvent = async () => {
  try {
    const token = localStorage.getItem('token')
    await axios.post('/events/', newEvent.value, {
      headers: { Authorization: `Bearer ${token}` }
    })
    showCreateModal.value = false
    newEvent.value = { title: '', description: '' }
    fetchEvents()
  } catch (err) {
    console.error('Error creating event:', err)
  }
}

onMounted(fetchEvents)
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-8">
    <div class="max-w-6xl mx-auto">
      <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Meine Events</h1>
        <button @click="showCreateModal = true"
          class="flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition">
          <Plus size="20" />
          Neues Event
        </button>
      </div>

      <div v-if="loading" class="text-center py-12">
        <p class="text-gray-500">Lade Events...</p>
      </div>

      <div v-else-if="events.length === 0" class="text-center py-12 bg-white rounded-xl shadow-sm">
        <CalendarIcon size="48" class="mx-auto text-gray-300 mb-4" />
        <p class="text-gray-500">Noch keine Events geplant.</p>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <router-link v-for="event in events" :key="event.id" :to="`/event/${event.id}`"
          class="bg-white p-6 rounded-xl shadow-sm hover:shadow-md transition border border-gray-100">
          <h2 class="text-xl font-semibold text-gray-900 mb-2">{{ event.title }}</h2>
          <p class="text-gray-600 line-clamp-2 mb-4">{{ event.description || 'Keine Beschreibung' }}</p>
          <div class="flex items-center text-sm text-gray-500">
            <span>Status: {{ event.is_closed ? 'Abgeschlossen' : 'In Abstimmung' }}</span>
          </div>
        </router-link>
      </div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-xl p-8 max-w-md w-full">
        <h2 class="text-2xl font-bold mb-6">Neues Event erstellen</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Titel</label>
            <input v-model="newEvent.title" type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500">
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Beschreibung</label>
            <textarea v-model="newEvent.description" rows="3"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-8">
          <button @click="showCreateModal = false" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
            Abbrechen
          </button>
          <button @click="createEvent"
            class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            Erstellen
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
