const SERVICES = {
    auth: window.AUTH_URL || "http://localhost:8000",
    patient: window.PATIENT_URL || "http://localhost:8001",
    doctor: window.DOCTOR_URL || "http://localhost:8002",
    appointment: window.APPOINTMENT_URL || "http://localhost:8003",
    records: window.RECORDS_URL || "http://localhost:8004",
    billing: window.BILLING_URL || "http://localhost:8006",
};

// ------------------------------
// Event bindings
// ------------------------------
document.getElementById("book-btn").onclick = bookAppointment;
document.getElementById("refresh-btn").onclick = () => {
    const user = document.getElementById('lookup-username')?.value || '';
    if(user) getAppointmentsByUsername(user);
    else getAppointments();
};
document.getElementById("load-doctors-btn").onclick = fetchDoctors;

// ------------------------------
// Init nav, top-user header, role-aware UI
// ------------------------------
function init() {
    const token = localStorage.getItem('access_token') || '';
    const role = localStorage.getItem('role') || '';

    const nav = document.querySelector('nav');
    if(nav){
        nav.style.display = 'flex';
        nav.style.gap = '12px';
        nav.style.alignItems = 'center';
        nav.innerHTML = '';

        const makeLink = (href, text, isPrimary=false) => {
            const a = document.createElement('a');
            a.href = href;
            a.style.textDecoration = 'none';
            a.style.color = isPrimary ? 'var(--primary)' : 'var(--muted)';
            if(isPrimary) a.style.fontWeight = '700';
            a.textContent = text;
            a.target = '_blank';
            return a;
        };

        nav.appendChild(makeLink(SERVICES.auth, 'Auth'));
        nav.appendChild(makeLink(SERVICES.patient, 'Patient'));
        nav.appendChild(makeLink(SERVICES.doctor, 'Doctor'));
        nav.appendChild(makeLink(SERVICES.appointment, 'Appointment', true));
        nav.appendChild(makeLink(SERVICES.records, 'Records'));
        nav.appendChild(makeLink(SERVICES.billing, 'Billing'));

        // show logout when a user is signed in
        if(role){
            const logoutBtn = document.createElement('button');
            logoutBtn.textContent = 'Logout';
            logoutBtn.style.marginLeft = 'auto';
            logoutBtn.style.padding = '6px 10px';
            logoutBtn.style.cursor = 'pointer';
            logoutBtn.onclick = function(){
                ['access_token','role','user_id','username','patient_name'].forEach(k => localStorage.removeItem(k));
                window.location.href = SERVICES.auth + '/';
            };
            nav.appendChild(logoutBtn);
        }

        // show/hide patient name input
        const pnameDiv = document.getElementById('patient-name');
        if(pnameDiv){
            if(role === 'patient'){
                pnameDiv.style.display = 'inline-block';
                const saved = localStorage.getItem('patient_name') || '';
                pnameDiv.value = saved;
                pnameDiv.addEventListener('change', e => localStorage.setItem('patient_name', e.target.value));
            } else pnameDiv.style.display = 'none';
        }
    }
}
document.addEventListener('DOMContentLoaded', init);

// ------------------------------
// Fetch specializations and doctors automatically
// ------------------------------
document.addEventListener('DOMContentLoaded', () => {
    fetchSpecializations().then(fetchDoctors).catch(err => { console.error('Specializations load error', err); fetchDoctors(); });
});

// ------------------------------
// Auth helper
// ------------------------------
function getToken() {
    return localStorage.getItem('access_token') || '';
}

// ------------------------------
// Appointment actions
// ------------------------------
function bookAppointment() {
    const doctor_id = parseInt(document.getElementById("doctor-id").value);
    const appointment_date = document.getElementById("appointment-date").value;
    const appointment_time = document.getElementById("appointment-time").value;
    const reason = document.getElementById("reason").value;

    fetch(`${SERVICES.appointment}/appointments`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${getToken()}`
        },
        body: JSON.stringify({ doctor_id, appointment_date, appointment_time, reason })
    })
    .then(res => res.json())
    .then(data => { alert("Appointment booked!"); getAppointments(); })
    .catch(err => alert("Error: " + err));
}

function getAppointments() {
    fetch(`${SERVICES.appointment}/appointments/my`, {
        headers: { "Authorization": `Bearer ${getToken()}` }
    })
    .then(res => res.ok ? res.json() : Promise.reject('Failed to load appointments'))
    .then(data => renderAppointmentsTable(data))
    .catch(err => { document.getElementById('appointments').innerText = 'No appointments or not authorized.'; });
}

function getAppointmentsByUsername(username) {
    fetch(`${SERVICES.appointment}/appointments/user/${encodeURIComponent(username)}`)
    .then(res => res.ok ? res.json() : Promise.reject('User not found or error'))
    .then(data => renderAppointmentsTable(data))
    .catch(err => { document.getElementById('appointments').innerText = 'No appointments found for that username.'; });
}

function cancelAppointment(id) {
    fetch(`${SERVICES.appointment}/appointments/${id}/cancel`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${getToken()}` }
    })
    .then(res => res.json())
    .then(data => { alert(data.message); getAppointments(); });
}

// ------------------------------
// Doctors and specializations
// ------------------------------
function fetchDoctors() {
    const sel = document.getElementById('filter-specialization');
    const specialization = sel?.value || '';
    let url = `${SERVICES.doctor}/doctors`;
    if(specialization && specialization !== 'all') url += `?specialization=${encodeURIComponent(specialization)}`;

    fetch(url)
    .then(res => res.json())
    .then(doctors => renderDoctors(doctors))
    .catch(err => alert('Error loading doctors: ' + err));
}

async function fetchSpecializations() {
    try {
        const res = await fetch(`${SERVICES.doctor}/specializations`);
        const data = await res.json();
        const sel = document.getElementById('filter-specialization');
        if(!sel) return;
        sel.innerHTML = '<option value="all">All specializations</option>';
        if(data?.specializations?.length){
            data.specializations.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                sel.appendChild(opt);
            });
        }
    } catch(e) {
        console.error('Failed to load specializations', e);
    }
}

function renderDoctors(doctors) {
    let html = "<table><tr><th>ID</th><th>Name</th><th>Specialization</th><th>Fee</th><th>Days</th><th>Actions</th></tr>";
    doctors.forEach(d => {
        html += `<tr>
            <td>${d.id}</td>
            <td>${d.first_name} ${d.last_name}</td>
            <td>${d.specialization}</td>
            <td>${d.consultation_fee}</td>
            <td>${d.available_days}</td>
            <td><button onclick="selectDoctor(${d.id})">Select</button></td>
        </tr>`;
    });
    html += "</table>";
    document.getElementById('doctors-list').innerHTML = html;
}

// ------------------------------
// Appointments table
// ------------------------------
function renderAppointmentsTable(data) {
    const pname = localStorage.getItem('patient_name') || '';
    let html = "";
    if(pname) html += `<div class="small">Appointments for: <strong>${pname}</strong></div>`;
    html += "<table><tr><th>ID</th><th>Doctor ID</th><th>Date</th><th>Time</th><th>Status</th><th>Reason</th><th>Actions</th></tr>";
    data.forEach(a => {
        html += `<tr>
            <td>${a.id}</td>
            <td>${a.doctor_id}</td>
            <td>${a.appointment_date}</td>
            <td>${a.appointment_time}</td>
            <td>${a.status}</td>
            <td>${a.reason || ""}</td>
            <td>${a.status === "scheduled" ? `<button onclick="cancelAppointment(${a.id})">Cancel</button>` : ""}</td>
        </tr>`;
    });
    html += "</table>";
    document.getElementById("appointments").innerHTML = html;
}

// ------------------------------
// Doctor selection
// ------------------------------
function selectDoctor(id) {
    document.getElementById('doctor-id').value = id;
    window.scrollTo(0, document.getElementById('doctor-id').offsetTop - 20);
}
