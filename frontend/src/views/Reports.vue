
<script setup>
import { ref, computed, onMounted } from 'vue'
import { getSessions, getSessionReport } from '../services/api'

const sessions = ref([])
const selectedSessionId = ref('')
const report = ref(null)

const loading = ref(false)
const error = ref('')

const summary = computed(() => report.value?.summary || {})

const formatDate = (date) => {
  if (!date) return '—'

  return new Date(date).toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

async function loadSessions() {
  try {
    sessions.value = await getSessions()

    if (sessions.value.length > 0) {
      selectedSessionId.value = String(sessions.value[0].session_id)
      await loadReport()
    }
  } catch (err) {
    error.value = err.message || 'Unable to load sessions'
  }
}

async function loadReport() {
  if (!selectedSessionId.value) return

  loading.value = true
  error.value = ''

  try {
    report.value = await getSessionReport(selectedSessionId.value)
  } catch (err) {
    report.value = null
    error.value = err.message || 'Unable to load report'
  } finally {
    loading.value = false
  }
}

function exportCSV() {
  if (!report.value) return

  const students = [
    ...(report.value.present_students || []),
    ...(report.value.absent_students || [])
  ]

  const rows = [
    ['Name', 'Roll Number', 'Department', 'Status', 'Timestamp'],
    ...students.map(student => [
      student.name,
      student.roll_number,
      student.department || '',
      student.status,
      student.timestamp || ''
    ])
  ]

  const csv = rows.map(row =>
    row.map(value =>
      `"${String(value ?? '').replace(/"/g, '""')}"`
    ).join(',')
  ).join('\n')

  const blob = new Blob(['\uFEFF' + csv], {
    type: 'text/csv;charset=utf-8;'
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `attendance_${selectedSessionId.value}.csv`
  link.click()

  URL.revokeObjectURL(url)
}

async function exportExcel() {
  if (!report.value) return

  try {
    const XLSX = await import('xlsx')

    const sessionSheet = XLSX.utils.json_to_sheet([{
      Subject: report.value.session.subject,
      'Session ID': report.value.session.session_id,
      'Total Enrolled': summary.value.total_enrolled,
      Present: summary.value.present,
      Absent: summary.value.absent,
      'Attendance Percentage': summary.value.attendance_percentage
    }])

    const studentRows = [
      ...(report.value.present_students || []),
      ...(report.value.absent_students || [])
    ].map(student => ({
      Name: student.name,
      'Roll Number': student.roll_number,
      Department: student.department || '',
      Status: student.status,
      Timestamp: student.timestamp || ''
    }))

    const studentSheet = XLSX.utils.json_to_sheet(studentRows)

    const workbook = XLSX.utils.book_new()

    XLSX.utils.book_append_sheet(
      workbook,
      sessionSheet,
      'Session Summary'
    )

    XLSX.utils.book_append_sheet(
      workbook,
      studentSheet,
      'Student Details'
    )

    XLSX.writeFile(
      workbook,
      `attendance_${selectedSessionId.value}.xlsx`
    )
  } catch (err) {
    error.value = 'Excel export failed. Check that xlsx is installed.'
  }
}

onMounted(loadSessions)
</script>

<template>
  <div class="reports-page">

    <div class="page-header">
      <div>
        <h1>Attendance Reports</h1>
        <p>View and analyze session-wise attendance records.</p>
      </div>

      <div class="export-buttons" v-if="report">
        <button class="export-btn csv-btn" @click="exportCSV">
          Export CSV
        </button>

        <button class="export-btn excel-btn" @click="exportExcel">
          Export Excel
        </button>
      </div>
    </div>

    <section class="session-selector">
      <label for="session">Select Attendance Session</label>

      <div class="selector-row">
        <select
          id="session"
          v-model="selectedSessionId"
          @change="loadReport"
        >
          <option value="" disabled>Select a session</option>

          <option
            v-for="session in sessions"
            :key="session.session_id"
            :value="String(session.session_id)"
          >
            {{ session.subject }} — Session #{{ session.session_id }}
            {{ session.is_active ? '(Active)' : '' }}
          </option>
        </select>

        <button @click="loadReport" :disabled="loading || !selectedSessionId">
          {{ loading ? 'Loading...' : 'Refresh Report' }}
        </button>
      </div>
    </section>

    <p v-if="error" class="error-message">{{ error }}</p>

    <div v-if="loading" class="empty-state">
      Loading attendance report...
    </div>

    <div v-else-if="!sessions.length" class="empty-state">
      No attendance sessions found.
    </div>

    <div v-else-if="report" class="report-content">

      <section class="session-info">
        <div>
          <span class="muted-label">SUBJECT</span>
          <h2>{{ report.session.subject }}</h2>
        </div>

        <div>
          <span class="muted-label">SESSION ID</span>
          <h2>#{{ report.session.session_id }}</h2>
        </div>

        <div>
          <span class="muted-label">STARTED AT</span>
          <h2>{{ formatDate(report.session.created_at) }}</h2>
        </div>

        <div>
          <span class="muted-label">STATUS</span>
          <span :class="report.session.is_active ? 'active-status' : 'inactive-status'">
            {{ report.session.is_active ? 'Active' : 'Completed' }}
          </span>
        </div>
      </section>

      <section class="stats-grid">
        <div class="stat-card">
          <span>Total Enrolled</span>
          <strong>{{ summary.total_enrolled ?? 0 }}</strong>
        </div>

        <div class="stat-card present-card">
          <span>Present</span>
          <strong>{{ summary.present ?? 0 }}</strong>
        </div>

        <div class="stat-card absent-card">
          <span>Absent</span>
          <strong>{{ summary.absent ?? 0 }}</strong>
        </div>

        <div class="stat-card percentage-card">
          <span>Attendance</span>
          <strong>{{ summary.attendance_percentage ?? 0 }}%</strong>
        </div>
      </section>

      <section class="percentage-section">
        <div class="percentage-heading">
          <h3>Attendance Overview</h3>
          <strong>{{ summary.attendance_percentage ?? 0 }}%</strong>
        </div>

        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: `${summary.attendance_percentage || 0}%` }"
          ></div>
        </div>
      </section>

      <section class="student-section">
        <h3>Present Students ({{ report.present_students.length }})</h3>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Roll Number</th>
                <th>Department</th>
                <th>Time</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              <tr
                v-for="(student, index) in report.present_students"
                :key="student.student_id"
              >
                <td>{{ index + 1 }}</td>
                <td>{{ student.name }}</td>
                <td>{{ student.roll_number }}</td>
                <td>{{ student.department || '—' }}</td>
                <td>{{ formatDate(student.timestamp) }}</td>
                <td><span class="present-badge">Present</span></td>
              </tr>

              <tr v-if="!report.present_students.length">
                <td colspan="6" class="no-data">No present students.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="student-section">
        <h3>Absent Students ({{ report.absent_students.length }})</h3>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Roll Number</th>
                <th>Department</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              <tr
                v-for="(student, index) in report.absent_students"
                :key="student.student_id"
              >
                <td>{{ index + 1 }}</td>
                <td>{{ student.name }}</td>
                <td>{{ student.roll_number }}</td>
                <td>{{ student.department || '—' }}</td>
                <td><span class="absent-badge">Absent</span></td>
              </tr>

              <tr v-if="!report.absent_students.length">
                <td colspan="5" class="no-data">No absent students.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

    </div>
  </div>
</template>

<style scoped>
.reports-page {
  color: #e5e7eb;
  padding: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 28px;
}

.page-header h1 {
  font-size: 27px;
  margin: 0 0 8px;
}

.page-header p {
  color: #94a3b8;
  margin: 0;
}

.export-buttons {
  display: flex;
  gap: 10px;
}

button {
  cursor: pointer;
  border: none;
  border-radius: 8px;
  padding: 11px 16px;
  color: white;
  background: #334155;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-btn:hover,
.selector-row button:hover {
  opacity: 0.85;
}

.csv-btn {
  background: #2563eb;
}

.excel-btn {
  background: #15803d;
}

.session-selector,
.session-info,
.percentage-section,
.student-section {
  background: #172033;
  border: 1px solid #273449;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 22px;
}

.session-selector label {
  display: block;
  color: #cbd5e1;
  margin-bottom: 10px;
}

.selector-row {
  display: flex;
  gap: 12px;
}

.selector-row select {
  flex: 1;
  min-width: 0;
  background: #0f172a;
  color: white;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px;
}

.selector-row button {
  background: #4f46e5;
}

.session-info {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.muted-label {
  display: block;
  color: #94a3b8;
  font-size: 11px;
  margin-bottom: 9px;
}

.session-info h2 {
  font-size: 16px;
  margin: 0;
  overflow-wrap: anywhere;
}

.active-status,
.inactive-status,
.present-badge,
.absent-badge {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 12px;
}

.active-status,
.present-badge {
  background: #14532d;
  color: #86efac;
}

.inactive-status,
.absent-badge {
  background: #7f1d1d;
  color: #fecaca;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 22px;
}

.stat-card {
  background: #172033;
  border: 1px solid #273449;
  border-radius: 12px;
  padding: 22px;
}

.stat-card span {
  display: block;
  color: #94a3b8;
  margin-bottom: 12px;
}

.stat-card strong {
  font-size: 30px;
}

.present-card strong {
  color: #4ade80;
}

.absent-card strong {
  color: #f87171;
}

.percentage-card strong {
  color: #818cf8;
}

.percentage-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.percentage-heading h3,
.student-section h3 {
  margin: 0 0 18px;
  font-size: 17px;
}

.percentage-heading h3 {
  margin: 0;
}

.progress-track {
  height: 12px;
  background: #334155;
  border-radius: 20px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #4f46e5;
  border-radius: 20px;
  transition: width 0.3s;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 650px;
}

th,
td {
  padding: 14px;
  text-align: left;
  border-bottom: 1px solid #273449;
  font-size: 13px;
}

th {
  color: #94a3b8;
  font-weight: 500;
}

td {
  color: #e2e8f0;
}

.no-data {
  text-align: center;
  color: #94a3b8;
  padding: 25px;
}

.empty-state {
  text-align: center;
  padding: 50px;
  color: #94a3b8;
}

.error-message {
  color: #fca5a5;
  margin: 15px 0;
}

@media (max-width: 900px) {
  .stats-grid,
  .session-info {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .selector-row {
    flex-direction: column;
  }

  .stats-grid,
  .session-info {
    grid-template-columns: 1fr;
  }
}
</style>
