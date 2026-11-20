
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import Faculty from './views/Faculty.vue'
import Students from './views/Students.vue'
import Attendance from './views/Attendance.vue'
import Reports from './views/Reports.vue'

import './style.css'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/faculty', component: Faculty },
  { path: '/students', component: Students },
  { path: '/attendance', component: Attendance },
  { path: '/reports', component: Reports }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

createApp(App).use(router).mount('#app')
