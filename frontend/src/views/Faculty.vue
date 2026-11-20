
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import {
  getActiveSession,
  startSession,
  endSession,
  getAttendance
} from '../services/api'

const subject = ref('')
const activeSession = ref(null)
const attendanceCount = ref(0)
const loading = ref(false)
const message = ref('')
const messageType = ref('success')

let refreshTimer = null

async function loadSession() {
  try {
    const data = await getActiveSession()
    activeSession.value = data.active ? data : null
  } catch (error) {
    console.error('Session loading failed:', error)
  }
}

async function loadAttendanceCount() {
  try {
    const records = await getAttendance()

    attendanceCount.value = activeSession.value
      ? records.filter(record =>
          record.session_id === activeSession.value.session_id &&
          record.status === 'present'
        ).length
      : 0
  } catch (error) {
    console.error('Attendance loading failed:', error)
  }
}

async function startAttendance() {
  if (!subject.value.trim()) {
    message.value = 'Please enter a subject name.'
    messageType.value = 'error'
    return
  }

  try {
    loading.value = true
    message.value = ''

    await startSession(subject.value.trim())

    subject.value = ''
    await loadSession()
    await loadAttendanceCount()

    message.value = 'Attendance session started successfully!'
    messageType.value = 'success'

  } catch (error) {
    message.value = error.message
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function stopAttendance() {
  if (!activeSession.value) return

  try {
    loading.value = true

    await endSession(activeSession.value.session_id)

    activeSession.value = null
    attendanceCount.value = 0

    message.value = 'Attendance session ended successfully!'
    messageType.value = 'success'

  } catch (error) {
    message.value = error.message
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadSession()
  await loadAttendanceCount()

  refreshTimer = setInterval(async () => {
    await loadSession()
    await loadAttendanceCount()
  }, 5000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>

<template>
  <div class="faculty-page">

    <div class="faculty-heading">
      <div>
        <h1>Faculty Dashboard</h1>
        <p>Manage classroom attendance sessions.</p>
      </div>

      <span class="faculty-tag">FACULTY PANEL</span>
    </div>

    <div v-if="message" :class="['alert', messageType]">
      {{ message }}
    </div>

    <div class="faculty-grid">

      <div class="panel session-panel">
        <h3>Start New Session</h3>
        <p class="panel-description">
          Select the subject and activate RFID attendance.
        </p>

        <form @submit.prevent="startAttendance">

          <label>Subject Name</label>

          <input
            v-model="subject"
            type="text"
            placeholder="e.g. Control Systems"
            :disabled="!!activeSession || loading"
          />

          <button
            type="submit"
            class="start-btn"
            :disabled="!!activeSession || loading"
          >
            {{ loading ? 'Please wait...' : '▶ Start Attendance' }}
          </button>

        </form>
      </div>

      <div class="panel active-panel">
        <div class="panel-header">
          <h3>Current Session</h3>

          <span :class="['session-badge', activeSession ? 'running' : 'stopped']">
            {{ activeSession ? 'ACTIVE' : 'INACTIVE' }}
          </span>
        </div>

        <div v-if="activeSession" class="active-details">
          <h2>{{ activeSession.subject }}</h2>

          <div class="counter">
            <strong>{{ attendanceCount }}</strong>
            <span>Students Present</span>
          </div>

          <button
            class="stop-btn"
            @click="stopAttendance"
            :disabled="loading"
          >
            ■ End Attendance
          </button>
        </div>

        <div v-else class="no-session">
          <div class="no-session-icon">◷</div>
          <h3>No Active Session</h3>
          <p>Start a session to allow students to scan their RFID cards.</p>
        </div>

      </div>

    </div>

    <div class="panel instructions-panel">
      <h3>How it works</h3>

      <div class="instruction-list">
        <div>01 <span>Enter the subject name.</span></div>
        <div>02 <span>Click Start Attendance.</span></div>
        <div>03 <span>Students scan their RFID cards.</span></div>
        <div>04 <span>End the session when the class finishes.</span></div>
      </div>
    </div>

  </div>
</template>
