
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// =====================================
// COMMON API REQUEST FUNCTION
// =====================================

async function apiRequest(endpoint, options = {}) {
  const isFormData = options.body instanceof FormData

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(options.body && !isFormData
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...options.headers
    }
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(
      data.detail || `API Error: ${response.status}`
    )
  }

  return data
}

// =====================================
// STUDENT APIs
// =====================================

export const getStudents = () =>
  apiRequest('/api/students')

export const registerStudent = (student) =>
  apiRequest('/api/students/register', {
    method: 'POST',
    body: JSON.stringify(student)
  })

// =====================================
// EXCEL STUDENT IMPORT
// =====================================

export const importStudents = (file) => {
  const formData = new FormData()

  formData.append('file', file)

  return apiRequest('/api/students/import', {
    method: 'POST',
    body: formData
  })
}

// =====================================
// RFID REGISTRATION
// =====================================

export const startRFIDRegistration = (studentId) =>
  apiRequest('/api/rfid/registration/start', {
    method: 'POST',
    body: JSON.stringify({
      student_id: studentId
    })
  })

// =====================================
// ATTENDANCE APIs
// =====================================

export const getAttendance = () =>
  apiRequest('/api/attendance')

export const getActiveSession = () =>
  apiRequest('/api/sessions/active')

export const startSession = (subject) =>
  apiRequest('/api/sessions/start', {
    method: 'POST',
    body: JSON.stringify({ subject })
  })

export const endSession = (session_id) =>
  apiRequest('/api/sessions/end', {
    method: 'POST',
    body: JSON.stringify({ session_id })
  })

// =====================================
// SESSION APIs
// =====================================

export const getSessions = () =>
  apiRequest('/api/sessions')

export const getSessionReport = (sessionId) =>
  apiRequest(`/api/sessions/${sessionId}/report`)
