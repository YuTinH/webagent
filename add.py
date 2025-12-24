import os

# 新的 doctors.html 内容 (修复了 ID)
NEW_DOCTORS_HTML = r'''<!doctype html>
<html lang="en">
<head>
<script>window.RelRoot = "../";</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Find a Doctor - Health Connect</title>
<link rel="stylesheet" href="../static/skin.css">
<link rel="stylesheet" href="../static/components.css">
<style>
.doctor-card {
  display: flex;
  gap: 24px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
  transition: var(--transition);
}
.doctor-card:hover {
  border-color: var(--ok);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
.doctor-avatar {
  width: 100px;
  height: 100px;
  background: var(--panel-elevated);
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 48px;
  flex-shrink: 0;
}
.doctor-info h3 {
  margin-top: 0;
  margin-bottom: 8px;
  color: var(--text-heading);
}
.doctor-meta {
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 8px;
}
</style>
</head>
<body>

<div class="navbar">
  <div class="inner">
    <div class="brand">
      <div class="logo" style="background: linear-gradient(135deg, #10b981, #6ee7b7)"></div>
      Health Connect
    </div>
    <div class="navlinks">
      <a href="index.html">Home</a>
      <a href="doctors.html" class="active">Doctors</a>
      <a href="records.html">My Records</a>
    </div>
  </div>
</div>

<div class="container">
  
  <div class="breadcrumbs">
    <a href="index.html">Home</a> / <span>Find a Doctor</span>
  </div>

  <h1 style="margin-bottom: 24px;">Find a Doctor</h1>

  <div class="grid cols-4" style="align-items:start">
    <div class="card" style="grid-column: span 1">
      <h3 style="margin-top:0; margin-bottom: 24px;">Filters</h3>
      <div class="mb-4">
        <label class="muted">Specialty</label>
        <select class="input mt-1">
          <option>All</option>
          <option>General Practice</option>
          <option>Cardiology</option>
          <option>Pediatrics</option>
          <option>Dermatology</option>
        </select>
      </div>
      <div class="mb-4">
        <label class="muted">Availability</label>
        <input type="date" class="input mt-1">
      </div>
      <button class="btn pri" style="width:100%" onclick="Toast.info('Filtering doctors (mock)')">Apply Filters</button>
    </div>

    <div style="grid-column: span 3">
      <div id="doctor-directory">
        <div class="doctor-card skeleton">
          <div class="doctor-avatar"></div>
          <div style="flex:1">
            <h3 class="skeleton" style="width:70%; height:28px; margin-bottom:8px"></h3>
            <div class="skeleton" style="width:40%; height:20px"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

</div>

<script src="../static/common.js"></script>
<script src="../static/components.js"></script>
<script>
const DOCTORS = [
  { id: 'DR-001', name: 'Dr. Alice Smith', specialty: 'General Practice', avatar: '👩‍⚕️' },
  { id: 'DR-002', name: 'Dr. Bob Johnson', specialty: 'Cardiology', avatar: '👨‍⚕️' },
  { id: 'DR-003', name: 'Dr. Carol White', specialty: 'Pediatrics', avatar: '👩‍⚕️' },
  { id: 'DR-004', name: 'Dr. David Green', specialty: 'Dermatology', avatar: '👨‍⚕️' },
];

function renderDoctors() {
  // Update selector to match new ID
  const list = document.getElementById('doctor-directory');
  if (!list) return;
  
  list.innerHTML = DOCTORS.map(doc => `
    <div class="doctor-card" data-doctor-id="${doc.id}">
      <div class="doctor-avatar">${doc.avatar}</div>
      <div class="doctor-info">
        <h3>${doc.name}</h3>
        <div class="doctor-meta">${doc.specialty}</div>
        <div class="doctor-meta">📍 123 Health St, Suite 404</div>
        <button class="btn pri mt-4" onclick="bookAppointment('${doc.id}')">Book Appointment</button>
      </div>
    </div>
  `).join('');
}

function bookAppointment(doctorId) {
  window.location.href = `appointment.html?doctor=${doctorId}`;
}

renderDoctors();
</script>

</body>
</html>
'''

def fix_medical_chain():
    # 1. Update doctors.html
    path = 'sites/health.local/doctors.html'
    print(f"🔧 Fixing ID mismatch in {path}...")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(NEW_DOCTORS_HTML)
    
    # 2. (Optional) Check index.html just in case
    # The error report said it timed out on index.html step waiting for directory,
    # but the logic likely clicks a link on index.html to GO TO doctors.html.
    # So ensuring doctors.html has the right ID is the key.
    
    print("✅ Done. 'doctor-list' has been renamed to 'doctor-directory'.")

if __name__ == "__main__":
    fix_medical_chain()