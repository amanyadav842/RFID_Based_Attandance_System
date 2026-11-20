
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getAttendance, getStudents } from '../services/api'

// -------------------- STATE --------------------

const records = ref([])
const students = ref([])
const loading = ref(false)
const error = ref('')
const socketStatus = ref('disconnected')

const search = ref('')
const selectedStatus = ref('all')
const selectedSubject = ref('all')
const selectedSession = ref('all')
const startDate = ref('')
const endDate = ref('')

let attendanceSocket = null
let reconnectTimer = null
let shouldReconnect = true

// -------------------- LOAD DATA --------------------

async function loadAttendance() {
  loading.value = true
  error.value = ''

  try {
    const [attendanceData, studentData] = await Promise.all([
      getAttendance(),
      getStudents()
    ])

    records.value = Array.isArray(attendanceData)
      ? attendanceData
      : []

    students.value = Array.isArray(studentData)
      ? studentData
      : []

    sortRecords()
  } catch (err) {
    console.error(err)
    error.value = err.message || 'Unable to load attendance data.'
  } finally {
    loading.value = false
  }
}

function sortRecords() {
  records.value.sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  )
}

// -------------------- WEBSOCKET --------------------

function connectAttendanceSocket() {
  if (!shouldReconnect) return

  const apiUrl = import.meta.env.VITE_API_BASE_URL

  if (!apiUrl) {
    socketStatus.value = 'disconnected'
    return
  }

  const wsUrl = apiUrl
    .replace(/^http/, 'ws')
    .replace(/\/$/, '')

  socketStatus.value = 'connecting'

  try {
    attendanceSocket = new WebSocket(
      `${wsUrl}/ws/attendance`
    )

    attendanceSocket.onopen = async () => {
      socketStatus.value = 'connected'

      // Recover records missed during a disconnection.
      try {
        const data = await getAttendance()
        if (Array.isArray(data)) {
          const byId = new Map(
            records.value.map(record => [record.id, record])
          )

          data.forEach(record => byId.set(record.id, record))
          records.value = [...byId.values()]
          sortRecords()
        }
      } catch (err) {
        console.error('WebSocket sync failed:', err)
      }
    }

    attendanceSocket.onmessage = event => {
      try {
        const message = JSON.parse(event.data)

        if (message.type === 'attendance_marked') {
          const record = message.data

          const exists = records.value.some(
            item => item.id === record.id
          )

          if (!exists) {
            records.value.unshift(record)
            sortRecords()
          }
        }
      } catch (err) {
        console.error('WebSocket message error:', err)
      }
    }

    attendanceSocket.onerror = err => {
      console.error('WebSocket error:', err)
      socketStatus.value = 'disconnected'
    }

    attendanceSocket.onclose = () => {
      socketStatus.value = 'disconnected'

      if (shouldReconnect) {
        reconnectTimer = setTimeout(
          connectAttendanceSocket,
          3000
        )
      }
    }
  } catch (err) {
    console.error('WebSocket connection failed:', err)
    socketStatus.value = 'disconnected'

    if (shouldReconnect) {
      reconnectTimer = setTimeout(
        connectAttendanceSocket,
        3000
      )
    }
  }
}

// -------------------- HELPERS --------------------

function localDateKey(timestamp) {
  const date = new Date(timestamp)

  if (Number.isNaN(date.getTime())) return ''

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  })
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function studentRoll(student) {
  return student.roll_number || ''
}

function sessionKey(record) {
  return record.session_id == null
    ? ''
    : String(record.session_id)
}

// -------------------- FILTER OPTIONS --------------------

const subjects = computed(() => {
  return [...new Set(
    records.value
      .map(record => record.subject)
      .filter(Boolean)
  )].sort()
})

const sessions = computed(() => {
  const map = new Map()

  for (const record of records.value) {
    if (record.session_id == null) continue

    if (
      selectedSubject.value !== 'all' &&
      record.subject !== selectedSubject.value
    ) continue

    const id = String(record.session_id)

    if (!map.has(id)) {
      map.set(id, {
        id,
        subject: record.subject,
        date: localDateKey(record.timestamp)
      })
    }
  }

  return [...map.values()].sort(
    (a, b) => Number(b.id) - Number(a.id)
  )
})

// -------------------- FILTER RECORDS --------------------

const filteredRecords = computed(() => {
  const query = search.value.toLowerCase().trim()

  return records.value.filter(record => {
    if (
      query &&
      ![
        record.name,
        record.roll_number,
        record.subject,
        record.device_id
      ].some(value =>
        String(value || '').toLowerCase().includes(query)
      )
    ) return false

    if (
      selectedStatus.value !== 'all' &&
      record.status !== selectedStatus.value
    ) return false

    if (
      selectedSubject.value !== 'all' &&
      record.subject !== selectedSubject.value
    ) return false

    if (
      selectedSession.value !== 'all' &&
      sessionKey(record) !== selectedSession.value
    ) return false

    const date = localDateKey(record.timestamp)

    if (startDate.value && date < startDate.value) return false
    if (endDate.value && date > endDate.value) return false

    return true
  })
})

// -------------------- STATISTICS --------------------

const totalRecords = computed(() => filteredRecords.value.length)

const presentCount = computed(() =>
  filteredRecords.value.filter(
    record => record.status === 'present'
  ).length
)

const todayCount = computed(() => {
  const today = localDateKey(new Date())

  return filteredRecords.value.filter(
    record => localDateKey(record.timestamp) === today
  ).length
})

// These are sessions with at least one attendance record.
const visibleSessionIds = computed(() => {
  return [...new Set(
    filteredRecords.value
      .filter(record => record.session_id != null)
      .map(record => String(record.session_id))
  )]
})

const totalSessions = computed(() => visibleSessionIds.value.length)

// -------------------- STUDENT REPORT --------------------

// Assumption: every registered student was expected in every
// session represented by the filtered attendance records.
// This is not a historical enrollment snapshot.

const studentReport = computed(() => {
  const sessionIds = visibleSessionIds.value

  return students.value.map(student => {
    const roll = studentRoll(student)

    const attended = new Set(
      filteredRecords.value
        .filter(record =>
          record.roll_number === roll &&
          record.status === 'present' &&
          record.session_id != null
        )
        .map(record => String(record.session_id))
    )

    const present = attended.size
    const total = sessionIds.length
    const absent = Math.max(0, total - present)

    return {
      name: student.name,
      roll_number: roll,
      department: student.department,
      total,
      present,
      absent,
      percentage: total
        ? Number((present / total * 100).toFixed(1))
        : null
    }
  }).filter(student => {
    const query = search.value.toLowerCase().trim()

    return !query || [
      student.name,
      student.roll_number,
      student.department
    ].some(value =>
      String(value || '').toLowerCase().includes(query)
    )
  })
})

const averageAttendance = computed(() => {
  const eligible = studentReport.value.filter(
    student => student.percentage !== null
  )

  if (!eligible.length) return null

  return (
    eligible.reduce(
      (sum, student) => sum + student.percentage,
      0
    ) / eligible.length
  ).toFixed(1)
})

// -------------------- DAILY TREND --------------------

const dailyTrend = computed(() => {
  const grouped = {}

  filteredRecords.value.forEach(record => {
    const date = localDateKey(record.timestamp)

    if (!date) return

    if (!grouped[date]) grouped[date] = 0

    if (record.status === 'present') {
      grouped[date]++
    }
  })

  return Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date, count }))
})

const maxDailyCount = computed(() =>
  Math.max(1, ...dailyTrend.value.map(day => day.count))
)

// -------------------- EXPORT --------------------

function exportRows() {
  return filteredRecords.value.map(record => ({
    Student: record.name,
    Roll_Number: record.roll_number,
    Subject: record.subject,
    Session_ID: record.session_id ?? '',
    Device_ID: record.device_id,
    Date: formatDate(record.timestamp),
    Time: formatTime(record.timestamp),
    Status: record.status
  }))
}

function csvCell(value) {
  const text = String(value ?? '')

  // Protect against spreadsheet formula injection.
  const safe = /^[\s]*[=+\-@]/.test(text)
    ? "'" + text
    : text

  return `"${safe.replace(/"/g, '""')}"`
}

function downloadCSV() {
  const rows = exportRows()

  if (!rows.length) return

  const headers = Object.keys(rows[0])

  const csv = [
    headers.map(csvCell).join(','),
    ...rows.map(row =>
      headers.map(key => csvCell(row[key])).join(',')
    )
  ].join('\r\n')

  const blob = new Blob(
    ['\uFEFF', csv],
    { type: 'text/csv;charset=utf-8;' }
  )

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = 'attendance-report.csv'
  link.click()

  URL.revokeObjectURL(url)
}

async function downloadExcel() {
  try {
    const XLSX = await import('xlsx')

    const safeExcelValue = value => {
      if (typeof value !== 'string') return value
      return /^[\s]*[=+\-@]/.test(value)
        ? "'" + value
        : value
    }

    const safeRows = rows => rows.map(row =>
      Object.fromEntries(
        Object.entries(row).map(
          ([key, value]) => [key, safeExcelValue(value)]
        )
      )
    )

    const workbook = XLSX.utils.book_new()

    const attendanceSheet = XLSX.utils.json_to_sheet(
      safeRows(exportRows())
    )

    const studentsSheet = XLSX.utils.json_to_sheet(
      safeRows(studentReport.value.map(student => ({
        Name: student.name,
        Roll_Number: student.roll_number,
        Department: student.department,
        Sessions: student.total,
        Present: student.present,
        Absent: student.absent,
        Percentage: student.percentage ?? 'N/A'
      })))
    )

    XLSX.utils.book_append_sheet(
      workbook, attendanceSheet, 'Attendance'
    )

    XLSX.utils.book_append_sheet(
      workbook, studentsSheet, 'Students'
    )

    XLSX.writeFile(workbook, 'attendance-report.xlsx')
  } catch (err) {
    console.error(err)
    error.value = 'Excel export failed. Check that xlsx is installed.'
  }
}

function resetFilters() {
  search.value = ''
  selectedStatus.value = 'all'
  selectedSubject.value = 'all'
  selectedSession.value = 'all'
  startDate.value = ''
  endDate.value = ''
}

// -------------------- LIFECYCLE --------------------

onMounted(() => {
  loadAttendance()
  connectAttendanceSocket()
})

onUnmounted(() => {
  shouldReconnect = false

  if (reconnectTimer) clearTimeout(reconnectTimer)

  if (attendanceSocket) {
    attendanceSocket.onclose = null
    attendanceSocket.close()
    attendanceSocket = null
  }
})
</script>

<template>
  <div class="attendance-page">

    <div class="attendance-heading">
      <div>
        <h1>Attendance Reports</h1>
        <p>Live RFID attendance, analytics and reports.</p>
      </div>

      <div class="attendance-heading-actions">
        <span :class="['connection-badge', socketStatus]">
          <span class="connection-dot"></span>
          {{ socketStatus === 'connected'
            ? 'Live Connected'
            : socketStatus === 'connecting'
              ? 'Connecting...'
              : 'Disconnected' }}
        </span>

        <button
          class="attendance-refresh"
          :disabled="loading"
          @click="loadAttendance"
        >
          {{ loading ? 'Loading...' : '↻ Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="alert error">
      {{ error }}
    </div>

    <!-- REPORT FILTERS -->
    <div class="panel report-filter-panel">
      <h3>Report Filters</h3>

      <div class="report-filter-grid">
        <input
          v-model="search"
          placeholder="Search student or roll number"
        />

        <select
          v-model="selectedSubject"
          @change="selectedSession = 'all'"
        >
          <option value="all">All Subjects</option>
          <option
            v-for="subject in subjects"
            :key="subject"
            :value="subject"
          >
            {{ subject }}
          </option>
        </select>

        <select v-model="selectedSession">
          <option value="all">All Sessions</option>
          <option
            v-for="session in sessions"
            :key="session.id"
            :value="session.id"
          >
            #{{ session.id }} - {{ session.subject }}
          </option>
        </select>

        <select v-model="selectedStatus">
          <option value="all">All Status</option>
          <option value="present">Present</option>
        </select>

        <label class="report-date-field">
          <span>From date</span>
          <input v-model="startDate" type="date" />
        </label>

        <label class="report-date-field">
          <span>To date</span>
          <input v-model="endDate" type="date" />
        </label>
      </div>

      <div class="report-actions">
        <button @click="resetFilters">Clear Filters</button>

        <button
          :disabled="!filteredRecords.length"
          @click="downloadCSV"
        >
          Export CSV
        </button>

        <button @click="downloadExcel">
          Export Excel
        </button>
      </div>
    </div>

    <!-- STATISTICS -->
    <div class="report-stats">
      <div class="panel attendance-stat">
        <span>Total Records</span>
        <h2>{{ totalRecords }}</h2>
        <small>Matching filters</small>
      </div>

      <div class="panel attendance-stat">
        <span>Present Records</span>
        <h2>{{ presentCount }}</h2>
        <small>Successful check-ins</small>
      </div>

      <div class="panel attendance-stat">
        <span>Today's Records</span>
        <h2>{{ todayCount }}</h2>
        <small>Matching records today</small>
      </div>

      <div class="panel attendance-stat">
        <span>Sessions</span>
        <h2>{{ totalSessions }}</h2>
        <small>Sessions with check-ins</small>
      </div>

      <div class="panel attendance-stat">
        <span>Average Attendance</span>
        <h2>
          {{ averageAttendance === null
            ? 'N/A'
            : averageAttendance + '%' }}
        </h2>
        <small>Estimated from registered students</small>
      </div>
    </div>

    <!-- ATTENDANCE TREND -->
    <div class="panel report-chart-panel">
      <h3>Daily Attendance Trend</h3>
      <p>Successful RFID check-ins per day</p>

      <div v-if="dailyTrend.length" class="report-chart">
        <div
          v-for="day in dailyTrend"
          :key="day.date"
          class="report-chart-item"
        >
          <strong>{{ day.count }}</strong>

          <div class="report-chart-track">
            <div
              class="report-chart-bar"
              :style="{
                height: `${day.count / maxDailyCount * 100}%`
              }"
            ></div>
          </div>

          <small>{{ day.date.slice(5) }}</small>
        </div>
      </div>

      <p v-else>No data for selected filters.</p>
    </div>

    <!-- STUDENT SUMMARY -->
    <div class="panel attendance-table-panel">
      <div class="attendance-table-heading">
        <div>
          <h3>Student Attendance Summary</h3>
          <p>Estimated attendance across selected sessions.</p>
        </div>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Roll Number</th>
              <th>Sessions</th>
              <th>Present</th>
              <th>Absent</th>
              <th>Attendance %</th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="student in studentReport"
              :key="student.roll_number"
            >
              <td>{{ student.name }}</td>
              <td>{{ student.roll_number }}</td>
              <td>{{ student.total }}</td>
              <td>{{ student.present }}</td>
              <td>{{ student.absent }}</td>
              <td>
                <span
                  v-if="student.percentage !== null"
                  :class="[
                    'attendance-badge',
                    student.percentage >= 75
                      ? 'present'
                      : 'other'
                  ]"
                >
                  {{ student.percentage }}%
                </span>
                <span v-else>N/A</span>
              </td>
            </tr>

            <tr v-if="!studentReport.length">
              <td colspan="6" class="empty-row">
                No registered students found.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="report-note">
        Note: This estimate assumes every currently registered
        student was expected in each displayed session.
        Sessions with no check-ins cannot be counted yet.
      </p>
    </div>

    <!-- ATTENDANCE HISTORY -->
    <div class="panel attendance-table-panel">
      <div class="attendance-table-heading">
        <div>
          <h3>Attendance History</h3>
          <p>Live attendance records from your RFID system.</p>
        </div>

        <span class="record-count">
          {{ filteredRecords.length }} Records
        </span>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Roll Number</th>
              <th>Subject</th>
              <th>Session</th>
              <th>Device ID</th>
              <th>Date</th>
              <th>Time</th>
              <th>Status</th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="record in filteredRecords"
              :key="record.id"
            >
              <td class="attendance-student">
                {{ record.name }}
              </td>
              <td>{{ record.roll_number }}</td>
              <td>{{ record.subject }}</td>
              <td>{{ record.session_id ?? '—' }}</td>
              <td>{{ record.device_id }}</td>
              <td>{{ formatDate(record.timestamp) }}</td>
              <td>{{ formatTime(record.timestamp) }}</td>
              <td>
                <span
                  :class="[
                    'attendance-badge',
                    record.status === 'present'
                      ? 'present'
                      : 'other'
                  ]"
                >
                  {{ record.status }}
                </span>
              </td>
            </tr>

            <tr v-if="!filteredRecords.length">
              <td colspan="8" class="empty-row">
                {{ loading
                  ? 'Loading attendance records...'
                  : 'No attendance records found.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="attendance-footer">
        Showing {{ filteredRecords.length }}
        of {{ records.length }} records

        <span v-if="socketStatus === 'connected'">
          · Live updates enabled
        </span>
      </div>
    </div>
  </div>
</template>
