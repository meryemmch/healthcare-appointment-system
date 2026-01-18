document.getElementById("save-btn").onclick = saveRecord;
document.getElementById("refresh-btn").onclick = loadRecords;
document.getElementById("filter-btn").onclick = filterRecords;

const API_URL = "http://localhost:8004";

// initialize token from localStorage
function init(){
    const tok = localStorage.getItem('access_token');
    const role = localStorage.getItem('role') || '';
    const uid = localStorage.getItem('user_id') || '';
    if(tok && document.getElementById('token') && !document.getElementById('token').value) document.getElementById('token').value = tok;
    // top-user header removed (no persistent signed-in line)
    // role-aware nav: only show compact nav for patients
    const nav = document.querySelector('nav');
    if(nav){
        if(role === 'patient'){
            nav.style.display = 'flex'; nav.style.gap = '12px'; nav.style.alignItems = 'center';
            nav.innerHTML = '';
            const makeLink = (href, text) => { const a = document.createElement('a'); a.href = href; a.style.textDecoration = 'none'; a.style.color = 'var(--muted)'; a.textContent = text; return a; };
            nav.appendChild(makeLink('http://localhost:8003/', 'Appointment'));
        } else {
            nav.style.display = 'none';
        }
    }
}
document.addEventListener('DOMContentLoaded', init);

function saveRecord() {
    const recordId = document.getElementById("record-id").value;
    const patient_id = parseInt(document.getElementById("patient-id").value);
    const appointment_id = document.getElementById("appointment-id").value || null;
    const diagnosis = document.getElementById("diagnosis").value;
    const prescription = document.getElementById("prescription").value;
    const lab_results = document.getElementById("lab-results").value;
    const notes = document.getElementById("notes").value;
    const record_date = document.getElementById("record-date").value;
    const token = document.getElementById("token").value;

    const data = { patient_id, appointment_id, diagnosis, prescription, lab_results, notes, record_date };

    let url = `${API_URL}/records`;
    let method = "POST";

    if (recordId) {
        url = `${API_URL}/records/${recordId}`;
        method = "PUT";
    }

    fetch(url, {
        method: method,
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(resp => {
        alert("Record saved successfully!");
        loadRecords();
    })
    .catch(err => alert("Error: " + err));
}

function loadRecords() {
    fetch(`${API_URL}/records/my`, {
        headers: { "Authorization": `Bearer ${document.getElementById("token").value}` }
    })
    .then(res => res.json())
    .then(data => renderRecords(data));
}

function filterRecords() {
    const patientId = document.getElementById("filter-patient-id").value;
    if (!patientId) return loadRecords();

    fetch(`${API_URL}/records/patient/${patientId}`, {
        headers: { "Authorization": `Bearer ${document.getElementById("token").value}` }
    })
    .then(res => res.json())
    .then(data => renderRecords(data));
}

function renderRecords(records) {
    let html = "<table><tr><th>ID</th><th>Patient</th><th>Doctor</th><th>Appointment</th><th>Diagnosis</th><th>Prescription</th><th>Lab Results</th><th>Notes</th><th>Date</th></tr>";
    records.forEach(r => {
        html += `<tr>
            <td>${r.id}</td>
            <td>${r.patient_id}</td>
            <td>${r.doctor_id}</td>
            <td>${r.appointment_id || ""}</td>
            <td>${r.diagnosis}</td>
            <td>${r.prescription || ""}</td>
            <td>${r.lab_results || ""}</td>
            <td>${r.notes || ""}</td>
            <td>${r.record_date}</td>
        </tr>`;
    });
    html += "</table>";
    document.getElementById("records-list").innerHTML = html;
}

// Initial load (if token present)
if(document.getElementById("token").value) loadRecords();
