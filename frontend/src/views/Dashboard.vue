

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getStudents, getAttendance } from '../services/api'

const students = ref([])
const attendanceRecords = ref([])
const loading = ref(true)
const error = ref('')

const todayAttendance = computed(() => {
  const today = new Date().toDateString()

  return attendanceRecords.value.filter(record =>
    new Date(record.timestamp).toDateString() === today &&
    record.status === 'present'
  )
})

const presentStudents = computed(() =>
  new Set(todayAttendance.value.map(record => record.roll_number)).size
)

const totalStudents = computed(() => students.value.length)

const absentStudents = computed(() =>
  Math.max(0, totalStudents.value - presentStudents.value)
)

const attendanceRate = computed(() =>
  totalStudents.value
    ? Math.round((presentStudents.value / totalStudents.value) * 100)
    : 0
)

const stats = computed(() => [
  {
    title: 'Total Students',
    value: totalStudents.value,
    icon: '♙',
    color: 'blue'
  },
  {
    title: 'Present Today',
    value: presentStudents.value,
    icon: '✓',
    color: 'green'
  },
  {
    title: 'Absent Today',
    value: absentStudents.value,
    icon: '✕',
    color: 'red'
  },
  {
    title: 'Attendance Rate',
    value: `${attendanceRate.value}%`,
    icon: '%',
    color: 'purple'
  }
])

const recentAttendance = computed(() =>
  [...todayAttendance.value]
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 5)
)

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadDashboard() {
  try {
    loading.value = true
    error.value = ''

    const [studentData, attendanceData] = await Promise.all([
      getStudents(),
      getAttendance()
    ])

    students.value = studentData
    attendanceRecords.value = attendanceData

  } catch (err) {
    console.error(err)
    error.value = 'Unable to load dashboard data. Check your backend.'
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>


<template>
  <div class="dashboard">
    <p v-if="error" style="color: red;">{{ error }}</p>
    <div class="welcome-section">
      <div>
        <h1>Dashboard Overview</h1>
        <p>Monitor your classroom attendance and student activity.</p>
      </div>

      <RouterLink to="/attendance" class="primary-btn">
        View Attendance →
      </RouterLink>
    </div>

    <!-- Statistics -->
    <div class="stats-grid">
      <div
        v-for="stat in stats"
        :key="stat.title"
        class="stat-card"
      >
        <div class="stat-top">
          <span>{{ stat.title }}</span>
          <div :class="['stat-icon', stat.color]">
            {{ stat.icon }}
          </div>
        </div>

        <h2>{{ stat.value }}</h2>
        <small>Live database data</small>
      </div>
    </div>

    <!-- Main content -->
    <div class="dashboard-grid">

      <div class="panel">
        <div class="panel-header">
          <div>
            <h3>Attendance Overview</h3>
            <p>Today's attendance summary</p>
          </div>
          <span class="live-label">TODAY</span>
        </div>

        <div class="empty-chart">
          <div class="chart-symbol">▥</div>
          <h3>Attendance analytics</h3>
          <p>Chart data will appear after connecting the backend.</p>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h3>Session Status</h3>
            <p>Current classroom session</p>
          </div>
        </div>

        <div class="session-status">
          <div class="session-indicator inactive"></div>
          <div>
            <strong>Session API unavailable</strong>
            <p>We will connect session management separately.</p>
          </div>
        </div>

        <RouterLink to="/faculty" class="action-btn">
          Manage Attendance Session →
        </RouterLink>
      </div>

    </div>

    <!-- Recent attendance -->
    <div class="panel recent-panel">
      <div class="panel-header">
        <div>
          <h3>Recent Attendance</h3>
          <p>Latest student check-ins</p>
        </div>

        <RouterLink to="/attendance" class="view-link">
          View all →
        </RouterLink>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Roll Number</th>
              <th>Time</th>
              <th>Status</th>
            </tr>
          </thead>

          <tbody v-if="recentAttendance.length">
            <tr v-for="(item, index) in recentAttendance" :key="index">
              <td>{{ item.name }}</td>
              <td>{{ item.roll_number }}</td>
              <td>{{ formatTime(item.timestamp) }}</td>
              <td>
                <span class="present-badge">{{ item.status }}</span>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td colspan="4" class="empty-row">
              {{ loading ? 'Loading attendance...' : 'No attendance records today.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>
