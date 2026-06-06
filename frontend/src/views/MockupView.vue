<template>
  <div class="vote-root">
    <!-- Error State -->
    <div v-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="header">
        <div class="event-title">{{ loading ? '…' : event?.title }}</div>
        <div class="event-sub">Abstimmung{{ loading ? '' : ` · ${proposals.length} Terminvorschläge` }}</div>
      </div>

      <!-- Loading: Platzhalter-Cards -->
      <div v-if="loading" class="proposals">
        <div v-for="i in 3" :key="i" class="card card-loading">
          <div class="skeleton skeleton-date"></div>
          <div class="skeleton skeleton-buttons"></div>
        </div>
      </div>

      <!-- Loaded State -->
      <div v-else class="proposals">
        <div
          v-for="p in proposals"
          :key="p.date"
          class="card"
          :class="{ highlighted: p.date === highlightDate }"
        >
          <div class="date-label">
            <span class="date-text">{{ formatDate(p.date) }}</span>
            <span v-if="p.date === highlightDate" class="badge">Dieser Termin</span>
          </div>

          <!-- Vote Buttons -->
          <div class="vote-buttons">
            <button
              v-for="opt in options"
              :key="opt.value"
              class="vote-btn"
              :class="[opt.cls, { active: p.my_vote === opt.value }]"
              :disabled="voting === p.date"
              @click="vote(p.date, opt.value)"
            >
              <span class="btn-icon">{{ opt.icon }}</span>
              <span class="btn-label">{{ opt.label }}</span>
            </button>
          </div>

          <!-- Abstimmungsstand -->
          <div class="vote-status">
            <div v-if="p.votes.best.length" class="status-row best">
              <span class="status-icon">✓</span>
              <span class="names">{{ p.votes.best.join(', ') }}</span>
            </div>
            <div v-if="p.votes.possible.length" class="status-row possible">
              <span class="status-icon">~</span>
              <span class="names">{{ p.votes.possible.join(', ') }}</span>
            </div>
            <div v-if="p.votes.impossible.length" class="status-row impossible">
              <span class="status-icon">✗</span>
              <span class="names">{{ p.votes.impossible.join(', ') }}</span>
            </div>
            <div v-if="p.votes.pending.length" class="status-row pending">
              <span class="status-icon">⏳</span>
              <span class="names">{{ p.votes.pending.join(', ') }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="footer-link">
        <a href="https://eventfinder.thunderbee.uk">Alle Details im EventFinder →</a>
      </div>
    </template>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="{ 'toast-ok': toast.ok, 'toast-err': !toast.ok }">
      {{ toast.msg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

// Types
interface VoteStatusEntry { best: string[]; possible: string[]; impossible: string[]; pending: string[] }
interface ProposalVoteState { date: string; my_vote: string | null; votes: VoteStatusEntry }
interface VoteEventInfo { id: string; title: string }

// State
const route = useRoute()
const eventId = route.params.eventId as string
const token = route.query.token as string
const highlightDate = (route.query.date as string | null) ?? null

const loading = ref(true)
const error = ref<string | null>(null)
const event = ref<VoteEventInfo | null>(null)
const proposals = ref<ProposalVoteState[]>([])
const voting = ref<string | null>(null)
const toast = ref<{ msg: string; ok: boolean } | null>(null)

const options = [
  { value: 'best',       icon: '✓', label: 'Perfekt',       cls: 'btn-best' },
  { value: 'possible',   icon: '~', label: 'Möglich',       cls: 'btn-possible' },
  { value: 'impossible', icon: '✗', label: 'Nicht möglich', cls: 'btn-impossible' },
]

// Fetch: GET /vote/{eventId}?token=
async function loadVotePage() {
  loading.value = true
  error.value = null
  try {
    const res = await axios.get(`/vote/${eventId}`, { params: { token } })
    event.value = res.data.event
    proposals.value = res.data.proposals
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Fehler beim Laden der Abstimmung.'
  } finally {
    loading.value = false
  }
}

// Vote: POST /vote/{eventId}/{date}?token=
async function vote(date: string, status: string) {
  if (voting.value) return

  // Find proposal and do optimistic update
  const proposal = proposals.value.find(p => p.date === date)
  if (!proposal) return

  const previousVote = proposal.my_vote
  proposal.my_vote = status

  voting.value = date
  try {
    const res = await axios.post(
      `/vote/${eventId}/${date}`,
      { status },
      { params: { token } }
    )
    // Update all proposals from response
    proposals.value = res.data
    showToast('Stimme gespeichert', true)
  } catch (e: any) {
    // Rollback optimistic update
    proposal.my_vote = previousVote
    const msg = e?.response?.data?.detail ?? 'Abstimmung fehlgeschlagen.'
    showToast(msg, false)
  } finally {
    voting.value = null
  }
}

// Format date for display: "2026-08-15" → "Sa., 15. August 2026"
function formatDate(d: string): string {
  const date = new Date(d + 'T00:00:00')
  return date.toLocaleDateString('de-DE', {
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

// Toast auto-hide nach 3s
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string, ok: boolean) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { msg, ok }
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

onMounted(loadVotePage)
</script>

<style scoped>
.vote-root {
  min-height: 100vh;
  background: #080b14;
  color: #fff;
  font-family: system-ui, sans-serif;
  padding: 0 0 40px;
  max-width: 480px;
  margin: 0 auto;
}

.header {
  padding: 28px 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.event-title { font-size: 20px; font-weight: 700; color: #06b6d4; }
.event-sub   { font-size: 13px; color: rgba(255,255,255,0.45); margin-top: 4px; }

.proposals { display: flex; flex-direction: column; gap: 12px; padding: 16px; }

.card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 16px;
  transition: border-color .2s;
}
.card.highlighted {
  border-color: #06b6d4;
  background: rgba(6,182,212,0.06);
}

.date-label {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.date-text { font-size: 15px; font-weight: 600; }
.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 20px;
  background: rgba(6,182,212,0.2);
  color: #06b6d4;
  font-weight: 500;
}

.vote-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-bottom: 14px;
}
.vote-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 13px 4px;
  min-height: 44px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  transition: all .15s;
  font-size: 12px;
}
.vote-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-icon  { font-size: 18px; }
.btn-label { font-size: 11px; font-weight: 500; }

.btn-best.active      { background: rgba(16,185,129,0.2); border-color: #10b981; color: #10b981; }
.btn-possible.active  { background: rgba(245,158,11,0.2); border-color: #f59e0b; color: #f59e0b; }
.btn-impossible.active{ background: rgba(239,68,68,0.2);  border-color: #ef4444; color: #ef4444; }

.vote-status { display: flex; flex-direction: column; gap: 4px; }
.status-row  { display: flex; align-items: baseline; gap: 8px; font-size: 12px; }
.status-icon { font-size: 11px; min-width: 14px; }
.names       { color: rgba(255,255,255,0.55); }

.best      .status-icon { color: #10b981; }
.possible  .status-icon { color: #f59e0b; }
.impossible .status-icon { color: #ef4444; }
.pending   .status-icon { color: rgba(255,255,255,0.3); }

.footer-link {
  text-align: center;
  padding-top: 8px;
}
.footer-link a {
  color: rgba(6,182,212,0.7);
  font-size: 13px;
  text-decoration: none;
}

/* Error message */
.error-msg {
  color: #ef4444;
  text-align: center;
  padding: 20px;
  font-size: 14px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  animation: fade-in .2s ease;
  pointer-events: none;
  white-space: nowrap;
}
.toast-ok  { background: rgba(16,185,129,0.9); color: #fff; }
.toast-err { background: rgba(239,68,68,0.9);  color: #fff; }

@keyframes fade-in {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* Skeleton loading cards */
.card-loading { pointer-events: none; }
.skeleton {
  background: rgba(255,255,255,0.06);
  border-radius: 6px;
  animation: shimmer 1.4s infinite;
}
.skeleton-date    { height: 18px; width: 60%; margin-bottom: 14px; }
.skeleton-buttons { height: 44px; width: 100%; }
@keyframes shimmer {
  0%, 100% { opacity: 0.5; }
  50%       { opacity: 1; }
}
</style>
