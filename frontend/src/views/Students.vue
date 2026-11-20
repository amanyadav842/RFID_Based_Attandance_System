
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

import {
  getStudents,
  registerStudent,
  importStudents,
  startRFIDRegistration
} from '../services/api'

const students = ref([])
const loading = ref(false)
const submitting = ref(false)
const importing = ref(false)

const search = ref('')
const showForm = ref(false)
const message = ref('')
const messageType = ref('success')

const fileInput = ref(null)

const registeringStudent = ref(null)
const registrationWaiting = ref(false)

let registrationTimer = null

const form = ref({
  name: '',
  roll_number: '',
  department: 'EEE',
  uid: ''
})

const filteredStudents = computed(() => {
  const query = search.value.toLowerCase().trim()

  if (!query) return students.value

  return students.value.filter(student =>
    (student.name || '').toLowerCase().includes(query) ||
    (student.roll_number || '').toLowerCase().includes(query) ||
    (student.department || '').toLowerCase().includes(query)
  )
})

const registeredCards = computed(() =>
  students.value.filter(student => student.rfid_registered).length
)

const pendingCards = computed(() =>
  students.value.length - registeredCards.value
)

function showMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
}

async function loadStudents() {
  try {
    loading.value = true
    students.value = await getStudents()
  } catch (error) {
    showMessage('Unable to load students. Check your backend.', 'error')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// =====================================
// MANUAL STUDENT REGISTRATION
// =====================================

async function submitStudent() {
  if (
    !form.value.name.trim() ||
    !form.value.roll_number.trim() ||
    !form.value.department.trim() ||
    !form.value.uid.trim()
  ) {
    showMessage('Please fill in all fields.', 'error')
    return
  }

  try {
    submitting.value = true
    message.value = ''

    const result = await registerStudent({
      name: form.value.name.trim(),
      roll_number: form.value.roll_number.trim().toUpperCase(),
      department: form.value.department.trim(),
      uid: form.value.uid.trim().replace(/\s/g, '').toUpperCase()
    })

    showMessage(result.message || 'Student registered successfully!')

    form.value = {
      name: '',
      roll_number: '',
      department: 'EEE',
      uid: ''
    }

    showForm.value = false

    await loadStudents()

  } catch (error) {
    showMessage(error.message || 'Student registration failed.', 'error')
  } finally {
    submitting.value = false
  }
}

// =====================================
// EXCEL IMPORT
// =====================================

function openFilePicker() {
  fileInput.value?.click()
}

async function handleExcelImport(event) {
  const file = event.target.files?.[0]

  if (!file) return

  const validExtension = /\.(xlsx)$/i.test(file.name)

  if (!validExtension) {
    showMessage('Please select an .xlsx Excel file.', 'error')
    event.target.value = ''
    return
  }

  try {
    importing.value = true
    message.value = ''

    const result = await importStudents(file)

    showMessage(
      `Import completed: ${result.imported_count} students imported, ${result.skipped_count} skipped.`,
      result.imported_count > 0 || result.skipped_count === 0
        ? 'success'
        : 'error'
    )

    await loadStudents()

    if (result.skipped_students?.length) {
      console.table(result.skipped_students)
      console.log('Skipped Excel rows:', result.skipped_students)
    }

  } catch (error) {
    showMessage(error.message || 'Excel import failed.', 'error')
  } finally {
    importing.value = false
    event.target.value = ''
  }
}

// =====================================
// RFID CARD REGISTRATION
// =====================================

function stopRegistrationPolling() {
  if (registrationTimer) {
    clearTimeout(registrationTimer)
    registrationTimer = null
  }
}

async function checkRegistrationStatus() {
  try {
    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL}/api/rfid/registration/pending`
    )

    if (!response.ok) {
      throw new Error('Unable to check registration status')
    }

    const data = await response.json()

    if (
      data.pending &&
      Number(data.student_id) === Number(registeringStudent.value?.id)
    ) {
      registrationTimer = setTimeout(
        checkRegistrationStatus,
        2000
      )
      return
    }

    if (!data.pending) {
      stopRegistrationPolling()

      registrationWaiting.value = false

      const studentName = registeringStudent.value?.name

      registeringStudent.value = null

      await loadStudents()

      showMessage(
        `Registration process finished for ${studentName}. Check the RFID status in the student directory.`,
        'success'
      )

      return
    }

    // Another registration request is pending.
    registrationTimer = setTimeout(
      checkRegistrationStatus,
      2000
    )

  } catch (error) {
    console.error(error)

    registrationTimer = setTimeout(
      checkRegistrationStatus,
      3000
    )
  }
}

async function beginRFIDRegistration(student) {
  if (student.rfid_registered) {
    showMessage(
      `${student.name} already has an active RFID card.`,
      'error'
    )
    return
  }

  if (registrationWaiting.value) {
    showMessage('Another RFID registration is already in progress.', 'error')
    return
  }

  try {
    message.value = ''

    const result = await startRFIDRegistration(student.id)

    registeringStudent.value = student
    registrationWaiting.value = true

    showMessage(
      `Waiting for ${student.name} to scan an RFID card.`
    )

    console.log('RFID registration started:', result)

    stopRegistrationPolling()
    checkRegistrationStatus()

  } catch (error) {
    showMessage(
      error.message || 'Unable to start RFID registration.',
      'error'
    )
  }
}

onMounted(loadStudents)

onUnmounted(() => {
  stopRegistrationPolling()
})
</script>

<template>
  <div class="students-page">

    <!-- Page heading -->
    <div class="students-heading">
      <div>
        <h1>Student Management</h1>
        <p>Import students and manage their RFID cards.</p>
      </div>

      <div class="heading-actions">
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx"
          hidden
          @change="handleExcelImport"
        />

        <button
          class="refresh-btn"
          @click="openFilePicker"
          :disabled="importing"
        >
          {{ importing ? 'Importing...' : 'Import Excel' }}
        </button>

        <button
          class="add-student-btn"
          @click="showForm = !showForm"
        >
          {{ showForm ? 'Close Form ✕' : '+ Add Student' }}
        </button>
      </div>
    </div>

    <!-- Notification -->
    <div v-if="message" :class="['alert', messageType]">
      {{ message }}
    </div>

    <!-- Excel format information -->
    <div class="panel import-info">
      <strong>Excel file format</strong>
      <p>
        Your first row must contain these column names:
        <strong>Name, Roll Number, Department</strong>.
        Upload an .xlsx file to import students in bulk.
      </p>
    </div>

    <!-- RFID registration waiting panel -->
    <div v-if="registrationWaiting" class="panel registration-waiting">
      <div>
        <h3>Waiting for RFID Card Scan</h3>

        <p>
          Student: <strong>{{ registeringStudent?.name }}</strong>
        </p>

        <p>
          Roll Number:
          <strong>{{ registeringStudent?.roll_number }}</strong>
        </p>

        <p class="waiting-text">
          Ask the selected student to scan their RFID card on the ESP32 reader.
        </p>
      </div>

      <span class="waiting-indicator">Waiting...</span>
    </div>

    <!-- Statistics -->
    <div class="student-summary">
      <div class="panel summary-card">
        <span>Total Students</span>
        <h2>{{ students.length }}</h2>
        <small>Students in database</small>
      </div>

      <div class="panel summary-card">
        <span>Registered RFID Cards</span>
        <h2>{{ registeredCards }}</h2>
        <small>Active RFID assignments</small>
      </div>

      <div class="panel summary-card">
        <span>Pending RFID Registration</span>
        <h2>{{ pendingCards }}</h2>
        <small>Students without active cards</small>
      </div>
    </div>

    <!-- Manual registration form -->
    <div v-if="showForm" class="panel registration-panel">

      <div class="panel-heading">
        <div>
          <h3>Register New Student</h3>
          <p>Manual registration with an existing RFID UID.</p>
        </div>
      </div>

      <form @submit.prevent="submitStudent">

        <div class="student-form-grid">

          <div class="form-field">
            <label>Student Name</label>
            <input
              v-model="form.name"
              type="text"
              placeholder="Enter student name"
              required
            />
          </div>

          <div class="form-field">
            <label>Roll Number</label>
            <input
              v-model="form.roll_number"
              type="text"
              placeholder="e.g. BT24EEE020"
              required
            />
          </div>

          <div class="form-field">
            <label>Department</label>
            <select v-model="form.department" required>
              <option value="EEE">Electrical and Electronics Engineering</option>
              <option value="CSE">Computer Science Engineering</option>
              <option value="ECE">Electronics and Communication Engineering</option>
              <option value="ME">Mechanical Engineering</option>
              <option value="CE">Civil Engineering</option>
            </select>
          </div>

          <div class="form-field">
            <label>RFID UID</label>
            <input
              v-model="form.uid"
              type="text"
              placeholder="Enter existing RFID UID"
              required
            />
            <small>Use this only for manual registration.</small>
          </div>

        </div>

        <div class="form-actions">
          <button
            type="button"
            class="cancel-btn"
            @click="showForm = false"
          >
            Cancel
          </button>

          <button
            type="submit"
            class="submit-btn"
            :disabled="submitting"
          >
            {{ submitting ? 'Registering...' : 'Register Student' }}
          </button>
        </div>

      </form>
    </div>

    <!-- Student directory -->
    <div class="panel directory-panel">

      <div class="directory-heading">
        <div>
          <h3>Student Directory</h3>
          <p>Select a student to register their RFID card.</p>
        </div>

        <button class="refresh-btn" @click="loadStudents">
          ↻ Refresh
        </button>
      </div>

      <div class="search-box">
        <span>⌕</span>
        <input
          v-model="search"
          type="text"
          placeholder="Search by name, roll number or department..."
        />
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Student Name</th>
              <th>Roll Number</th>
              <th>Department</th>
              <th>RFID Status</th>
              <th>Action</th>
            </tr>
          </thead>

          <tbody v-if="filteredStudents.length">
            <tr
              v-for="student in filteredStudents"
              :key="student.id"
            >
              <td>#{{ student.id }}</td>

              <td class="student-name">
                {{ student.name }}
              </td>

              <td>{{ student.roll_number }}</td>

              <td>{{ student.department || '—' }}</td>

              <td>
                <span
                  v-if="student.rfid_registered"
                  class="registered-badge"
                >
                  RFID Registered
                </span>

                <span
                  v-else
                  class="absent-badge"
                >
                  Pending
                </span>
              </td>

              <td>
                <button
                  v-if="!student.rfid_registered"
                  class="submit-btn"
                  :disabled="registrationWaiting"
                  @click="beginRFIDRegistration(student)"
                >
                  Register RFID
                </button>

                <span v-else class="registered-badge">
                  Assigned
                </span>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td colspan="6" class="empty-row">
                {{ loading ? 'Loading students...' : 'No students found.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="directory-footer">
        Showing {{ filteredStudents.length }} of {{ students.length }} students
      </div>

    </div>

  </div>
</template>

<style scoped>
.heading-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.import-info {
  padding: 16px 20px;
  margin-bottom: 20px;
}

.import-info p {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.registration-waiting {
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #4f46e5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.registration-waiting h3 {
  margin: 0 0 12px;
}

.registration-waiting p {
  margin: 5px 0;
}

.waiting-text {
  color: #94a3b8;
  font-size: 13px;
}

.waiting-indicator {
  color: #fbbf24;
  background: #422006;
  border-radius: 20px;
  padding: 8px 14px;
  white-space: nowrap;
}

.absent-badge {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 20px;
  background: #422006;
  color: #fbbf24;
  font-size: 12px;
}

.registered-badge {
  display: inline-block;
  padding: 5px 10px;
  border-radius: 20px;
  background: #14532d;
  color: #86efac;
  font-size: 12px;
}

@media (max-width: 700px) {
  .heading-actions {
    width: 100%;
  }

  .registration-waiting {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
