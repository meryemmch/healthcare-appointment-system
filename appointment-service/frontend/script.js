// No auth token needed for now
document.getElementById("book-btn").onclick = bookAppointment;
document.getElementById("refresh-btn").onclick = () => {
    const user = document.getElementById('lookup-username') ? document.getElementById('lookup-username').value : '';
    if(user) getAppointmentsByUsername(user);
    else getAppointments();
};
document.getElementById("load-doctors-btn").onclick = fetchDoctors;

// initialize top-user header and role-aware nav (only patients see the top bar)
function init() {
    const token = localStorage.getItem('access_token') || '';
    const role = localStorage.getItem('role') || '';
    const uid = localStorage.getItem('user_id') || '';

    // top-user header removed (no persistent signed-in line)

    // Render compact top bar for this service (persisting Appointment / Records / Billing)
    const nav = document.querySelector('nav');
    if(nav){
        nav.style.display = 'flex'; nav.style.gap = '12px'; nav.style.alignItems = 'center';
        nav.innerHTML = '';
        const makeLink = (href, text) => { const a = document.createElement('a'); a.href = href; a.style.textDecoration = 'none'; a.style.color = 'var(--muted)'; a.textContent = text; return a; };
        nav.appendChild(makeLink('http://localhost:8003/', 'Appointment'));
        // show logout when a user is signed in
        const rolePresent = !!localStorage.getItem('role');
        if(rolePresent){
            const logoutBtn = document.createElement('button');
            logoutBtn.textContent = 'Logout';
            logoutBtn.style.marginLeft = 'auto';
            logoutBtn.style.padding = '6px 10px';
            logoutBtn.style.cursor = 'pointer';
            logoutBtn.onclick = function(){
                try{ localStorage.removeItem('access_token'); localStorage.removeItem('role'); localStorage.removeItem('user_id'); localStorage.removeItem('username'); }catch(e){}
                window.location.href = 'http://localhost:8000/';
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
                pnameDiv.addEventListener('change', (e)=>{
                    localStorage.setItem('patient_name', e.target.value);
                });
            } else {
                // hide for non-patients
                const p = document.getElementById('patient-name');
                if(p) p.style.display = 'none';
            }
        }
    }
}
document.addEventListener('DOMContentLoaded', init);

// also load doctors list automatically so patients see available doctors with specialization and fees
// load specializations first, then doctors
document.addEventListener('DOMContentLoaded', () => {
    fetchSpecializations().then(() => fetchDoctors()).catch(err => { console.error('specializations load error', err); fetchDoctors(); });
});

// initialize token from localStorage
function getToken(){
    return localStorage.getItem('access_token') || '';
}

function bookAppointment() {
    const doctor_id = document.getElementById("doctor-id").value;
    const appointment_date = document.getElementById("appointment-date").value;
    const appointment_time = document.getElementById("appointment-time").value;
    const reason = document.getElementById("reason").value;

    fetch("http://localhost:8003/appointments", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` },
        body: JSON.stringify({ doctor_id: parseInt(doctor_id), appointment_date, appointment_time, reason })
    })
    .then(res => res.json())
    .then(data => {
        alert("Appointment booked!");
        getAppointments();
    })
    .catch(err => alert("Error: " + err));
}

function getAppointments() {
    fetch("http://localhost:8003/appointments/my", { headers: { "Authorization": `Bearer ${getToken()}` } })
    .then(res => {
        if(!res.ok){
            throw new Error('Failed to load appointments');
        }
        return res.json();
    })
    .then(data => renderAppointmentsTable(data))
    .catch(err => { document.getElementById('appointments').innerText = 'No appointments or not authorized.'; });
}

function getAppointmentsByUsername(username){
    fetch(`http://localhost:8003/appointments/user/${encodeURIComponent(username)}`)
    .then(res => {
        if(!res.ok) throw new Error('User not found or error');
        return res.json();
    })
    .then(data => renderAppointmentsTable(data))
    .catch(err => { document.getElementById('appointments').innerText = 'No appointments found for that username.'; });
}

function renderAppointmentsTable(data){
    const pname = localStorage.getItem('patient_name') || '';
    let html = "";
    if(pname) html += `<div class=\"small\">Appointments for: <strong>${pname}</strong></div>`;
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

function cancelAppointment(id) {
    fetch(`http://localhost:8003/appointments/${id}/cancel`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${getToken()}` }
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        getAppointments();
    });
}

// Fetch doctors from doctor-service and render them for selection
function fetchDoctors(){
    const sel = document.getElementById('filter-specialization');
    const specialization = sel ? sel.value : '';
    let url = 'http://localhost:8002/doctors';
    if(specialization && specialization !== 'all') url += `?specialization=${encodeURIComponent(specialization)}`;
    fetch(url)
    .then(res => res.json())
    .then(doctors => renderDoctors(doctors))
    .catch(err => alert('Error loading doctors: ' + err));
}

async function fetchSpecializations(){
    try{
        const res = await fetch('http://localhost:8002/specializations');
        const data = await res.json();
        const sel = document.getElementById('filter-specialization');
        if(!sel) return;
        // clear except the 'all' option
        sel.innerHTML = '<option value="all">All specializations</option>';
        if(data && Array.isArray(data.specializations)){
            data.specializations.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                sel.appendChild(opt);
            });
        }
    } catch(e){
        console.error('Failed to load specializations', e);
    }
}

function renderDoctors(doctors){
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

function selectDoctor(id){
    document.getElementById('doctor-id').value = id;
    window.scrollTo(0, document.getElementById('doctor-id').offsetTop - 20);
}
