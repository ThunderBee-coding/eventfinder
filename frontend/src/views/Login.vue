<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const email = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')

const route = useRoute()
const router = useRouter()

const requestMagicLink = async () => {
  loading.ref = true
  error.value = ''
  message.value = ''
  try {
    await axios.post('/auth/magic-link', { email: email.value })
    message.value = 'Magic Link wurde gesendet! Bitte prüfe dein Postfach.'
  } catch (err) {
    error.value = 'Fehler beim Senden des Links.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const token = route.query.token as string
  if (token) {
    loading.value = true
    try {
      const response = await axios.get(`/auth/verify?token=${token}`)
      localStorage.setItem('token', response.data.access_token)
      router.push('/')
    } catch (err) {
      error.value = 'Ungültiger oder abgelaufener Link.'
    } finally {
      loading.value = false
    }
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-xl shadow-md">
      <div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">EventFinder</h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          Melde dich mit deinem Magic Link an
        </p>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="requestMagicLink">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="email-address" class="sr-only">E-Mail Adresse</label>
            <input v-model="email" id="email-address" name="email" type="email" autocomplete="email" required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
              placeholder="E-Mail Adresse">
          </div>
        </div>

        <div>
          <button type="submit" :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500">
            <span v-if="loading">Lädt...</span>
            <span v-else>Magic Link anfordern</span>
          </button>
        </div>
        
        <p v-if="message" class="text-green-600 text-sm text-center">{{ message }}</p>
        <p v-if="error" class="text-red-600 text-sm text-center">{{ error }}</p>
      </form>
    </div>
  </div>
</template>
