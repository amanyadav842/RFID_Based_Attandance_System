
<template>
  <aside class="sidebar">
    <!-- Brand -->
    <div class="brand">
      <div class="brand-icon">R</div>
      <div>
        <h2>RFID Attend</h2>
        <span>Attendance System</span>
      </div>
    </div>

    <!-- Navigation -->
    <p class="menu-label">MAIN MENU</p>

    <nav>
      <RouterLink to="/" class="nav-link" exact-active-class="active">
        <span>▦</span>
        Dashboard
      </RouterLink>

      <RouterLink to="/faculty" class="nav-link" active-class="active">
        <span>♙</span>
        Faculty
      </RouterLink>

      <RouterLink to="/students" class="nav-link" active-class="active">
        <span>♧</span>
        Students
      </RouterLink>

      <RouterLink to="/attendance" class="nav-link" active-class="active">
        <span>◷</span>
        Attendance
      </RouterLink>

      <RouterLink to="/reports" class="nav-link" active-class="active">
        <span>▤</span>
        Reports
      </RouterLink>
    </nav>

    <!-- Device Status -->
    <div class="sidebar-footer">
      <span class="status-dot"></span>
      ESP32 Device
      <span class="online-text">Online</span>
    </div>
  </aside>
</template>
