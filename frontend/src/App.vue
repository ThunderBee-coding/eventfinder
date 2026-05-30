<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
const logout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

const hasToken = () => !!localStorage.getItem('token')
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <nav v-if="$route.path !== '/login'" class="bg-white shadow-sm border-b">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <router-link to="/" class="text-2xl font-bold text-primary-600">EventFinder</router-link>
          </div>
          <div class="flex items-center gap-4">
            <button @click="logout" class="text-sm text-gray-500 hover:text-gray-700">Abmelden</button>
          </div>
        </div>
      </div>
    </nav>

    <main class="flex-grow">
      <router-view />
    </main>
  </div>
</template>
