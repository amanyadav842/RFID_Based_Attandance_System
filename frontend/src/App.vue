
<script setup>
import Sidebar from './components/Sidebar.vue'
</script>

<template>
  <div class="app-layout">

    <!-- Sidebar Component -->
    <Sidebar />

    <!-- Main Content -->
    <main class="main-content">

      <header class="topbar">
        <div>
          <h2>RFID Attendance Portal</h2>
          <p>Manage your classroom attendance</p>
        </div>

        <div class="profile">
          <div class="avatar">A</div>
          <div>
            <strong>Administrator</strong>
            <small>Admin Panel</small>
          </div>
        </div>
      </header>

      <!-- Dynamic Page Content -->
      <section class="page-content">
        <RouterView />
      </section>

    </main>
  </div>
</template>
