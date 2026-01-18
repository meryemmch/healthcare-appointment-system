function showMessage() {
    document.getElementById('output').innerText = 'Patient service action triggered!';
}

// initialize patient top bar and top-user header
function init(){
    const role = localStorage.getItem('role') || '';
    const uid = localStorage.getItem('user_id') || '';
    // top-user header removed (no persistent signed-in line)
    const container = document.querySelector('.container');
    const nav = document.querySelector('nav');
    // if a nav already exists in the HTML, prefer that; otherwise create one for patient role
    if(role === 'patient'){
        let navEl = nav || document.createElement('nav');
        navEl.style.display='flex'; navEl.style.gap='12px'; navEl.style.marginBottom='12px'; navEl.style.alignItems='center';
        navEl.innerHTML = '';
        const makeLink = (href, text) => { const a = document.createElement('a'); a.href = href; a.style.textDecoration='none'; a.style.color = 'var(--muted)'; a.textContent = text; return a; };
        navEl.appendChild(makeLink('http://localhost:8003/', 'Appointment'));
        // logout button at far right
        const logoutBtn = document.createElement('button');
        logoutBtn.textContent = 'Logout';
        logoutBtn.style.marginLeft = 'auto';
        logoutBtn.style.padding = '6px 10px';
        logoutBtn.style.cursor = 'pointer';
        logoutBtn.onclick = logoutAndRedirect;
        navEl.appendChild(logoutBtn);
        if(!nav) container.insertBefore(navEl, container.firstChild);
    } else if (role === 'doctor'){
        // show doctor+patient nav when a doctor signs in (doctor can navigate between doctor and patient views)
        let navEl = nav || document.createElement('nav');
        navEl.style.display='flex'; navEl.style.gap='12px'; navEl.style.marginBottom='12px'; navEl.style.alignItems='center';
        navEl.innerHTML = '';
        const makeLink = (href, text) => { const a = document.createElement('a'); a.href = href; a.style.textDecoration='none'; a.style.color = 'var(--muted)'; a.textContent = text; return a; };
        navEl.appendChild(makeLink('http://localhost:8002/', 'Doctor'));
        navEl.appendChild(makeLink('http://localhost:8001/', 'Patient'));
        navEl.appendChild(makeLink('http://localhost:8006/', 'Billing'));
        // logout button at far right
        const logoutBtn2 = document.createElement('button');
        logoutBtn2.textContent = 'Logout';
        logoutBtn2.style.marginLeft = 'auto';
        logoutBtn2.style.padding = '6px 10px';
        logoutBtn2.style.cursor = 'pointer';
        logoutBtn2.onclick = logoutAndRedirect;
        navEl.appendChild(logoutBtn2);
        if(!nav) container.insertBefore(navEl, container.firstChild);

        // fetch appointments for this doctor, then fetch each patient's latest record and render a combined patient list
        (async function(){
            try{
                const token = localStorage.getItem('access_token') || '';
                const apptResp = await fetch('http://localhost:8003/appointments/my', { headers: { 'Authorization': `Bearer ${token}` } });
                const appointments = await apptResp.json();
                const target = document.getElementById('output') || document.getElementById('patients-list') || (() => { const d=document.createElement('div'); d.id='patients-list'; container.appendChild(d); return d; })();
                if(!appointments || appointments.length === 0){ target.innerHTML = '<p class="small">No appointments found for you</p>'; return; }

                // group appointments by patient and find last appointment per patient
                const byPatient = {};
                appointments.forEach(a => {
                    const pid = a.patient_id;
                    if(!byPatient[pid]) byPatient[pid] = [];
                    byPatient[pid].push(a);
                });

                const patientIds = Object.keys(byPatient);
                // fetch latest record for each patient in parallel
                const recordPromises = patientIds.map(pid =>
                    fetch(`http://localhost:8004/records/patient/${pid}`, { headers: { 'Authorization': `Bearer ${token}` } })
                    .then(r => r.json()).catch(() => [])
                );

                const recordsForPatients = await Promise.all(recordPromises);

                // build table
                let html = '<h2>Patients with appointments</h2><table><tr><th>Patient ID</th><th>Last Appointment</th><th>Diagnosis (latest)</th></tr>';
                patientIds.forEach((pid, i) => {
                    const appts = byPatient[pid];
                    // sort appts to find last by date/time
                    appts.sort((a,b) => (a.appointment_date + ' ' + a.appointment_time) < (b.appointment_date + ' ' + b.appointment_time) ? 1 : -1);
                    const last = appts[0];
                    const recs = Array.isArray(recordsForPatients[i]) ? recordsForPatients[i] : [];
                    const latestRec = recs.length > 0 ? recs[0] : null;
                    html += `<tr><td>${pid}</td><td>${last.appointment_date} ${last.appointment_time}</td><td>${latestRec ? latestRec.diagnosis : ''}</td></tr>`;
                });
                html += '</table>';
                target.innerHTML = html;
            }catch(err){ const t = document.getElementById('patients-list'); if(t) t.innerText = 'Error loading patients'; console.error(err); }
        })();
    }
}
document.addEventListener('DOMContentLoaded', init);

function logoutAndRedirect(){
    try{
        localStorage.removeItem('access_token');
        localStorage.removeItem('role');
        localStorage.removeItem('user_id');
        localStorage.removeItem('username');
    }catch(e){}
    window.location.href = 'http://localhost:8000/';
}