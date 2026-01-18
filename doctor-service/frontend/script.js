const API_URL = "http://localhost:8003"; // appointments API

// initialize small UI and load appointments
function init(){
    const role = localStorage.getItem('role') || '';
    const nav = document.querySelector('nav');
    if(nav && role === 'doctor'){
        nav.style.display = 'flex'; nav.style.gap='12px'; nav.style.alignItems='center'; nav.innerHTML = '';
        const makeLink = (href, text) => { const a = document.createElement('a'); a.href = href; a.style.textDecoration='none'; a.style.color = 'var(--muted)'; a.textContent = text; return a; };
        nav.appendChild(makeLink('http://localhost:8002/', 'Doctor'));
        nav.appendChild(makeLink('http://localhost:8001/', 'Patient'));
        nav.appendChild(makeLink('http://localhost:8004/', 'Records'));
        nav.appendChild(makeLink('http://localhost:8006/', 'Billing'));
        // add logout button at the far right
        const logoutBtn = document.createElement('button');
        logoutBtn.textContent = 'Logout';
        logoutBtn.style.marginLeft = 'auto';
        logoutBtn.style.padding = '6px 10px';
        logoutBtn.style.cursor = 'pointer';
        logoutBtn.onclick = logoutAndRedirect;
        nav.appendChild(logoutBtn);
    }

    // Wire filter and refresh buttons
    const filterBtn = document.getElementById('filter-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    if(filterBtn) filterBtn.onclick = getDoctorAppointments;
    if(refreshBtn) refreshBtn.onclick = getDoctorAppointments;

    // Do not auto-load appointments on page load to avoid showing errors (fetch only on user action)
    const container = document.getElementById('appointments-list');
    if(container) container.innerHTML = '<p class="small">Press Refresh to load appointments</p>';
}

function logoutAndRedirect(){
    // Remove auth-related keys and redirect to auth login
    try{
        localStorage.removeItem('access_token');
        localStorage.removeItem('role');
        localStorage.removeItem('user_id');
        localStorage.removeItem('username');
    }catch(e){ /* ignore */ }
    // redirect to auth login page
    window.location.href = 'http://localhost:8000/';
}

document.addEventListener('DOMContentLoaded', init);

function getDoctorAppointments(){
    const token = localStorage.getItem('access_token') || '';
    const status = document.getElementById('filter-status') ? document.getElementById('filter-status').value : '';
    const date = document.getElementById('filter-date') ? document.getElementById('filter-date').value : '';
    let url = `${API_URL}/appointments/my`;
    const params = [];
    if(status) params.push(`status=${encodeURIComponent(status)}`);
    if(date) params.push(`date=${encodeURIComponent(date)}`);
    if(params.length) url += `?${params.join('&')}`;
    fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    .then(async res => {
        const text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch(e) { data = text; }
        if(!res.ok){
            const el = document.getElementById('appointments-list');
            const msg = (data && data.detail) ? data.detail : (typeof data === 'string' ? data : `Error ${res.status}`);
            if(el) el.innerHTML = `<p class="small error">${msg}</p>`;
            console.error('Appointments API error', res.status, data);
            return;
        }
        // successful
        renderAppointments(data || []);
    })
    .catch(err => { const el = document.getElementById('appointments-list'); if(el) el.innerText = 'Error loading appointments'; console.error(err); });
}

function renderAppointments(appts){
    const container = document.getElementById('appointments-list');
    if(!appts || (Array.isArray(appts) && appts.length === 0)){
        container.innerHTML = '<p class="small">No appointments found</p>'; return; }
    if(!Array.isArray(appts)){
        // likely an error object
        const msg = appts.detail || JSON.stringify(appts);
        container.innerHTML = `<p class="small error">${msg}</p>`; return;
    }
    let html = '<table><tr><th>ID</th><th>Patient ID</th><th>Date</th><th>Time</th><th>Status</th><th>Reason</th><th>Actions</th></tr>';
    appts.forEach(a => {
        html += `<tr>
            <td>${a.id}</td>
            <td>${a.patient_id}</td>
            <td>${a.appointment_date}</td>
            <td>${a.appointment_time}</td>
            <td>${a.status}</td>
            <td>${a.reason || ''}</td>
            <td>${a.status === 'scheduled' ? `<button onclick="completeAppointment(${a.id})">Complete</button>` : ''}</td>
        </tr>`;
    });
    html += '</table>';
    container.innerHTML = html;
}

function completeAppointment(id){
    const token = localStorage.getItem('access_token') || '';
    fetch(`http://localhost:8003/appointments/${id}/complete`, { method: 'PUT', headers: { 'Authorization': `Bearer ${token}` } })
    .then(res => res.json())
    .then(j => { alert(j.message || 'Completed'); getDoctorAppointments(); })
    .catch(err => alert('Error: ' + err));
}
