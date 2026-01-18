const roleSelect = document.getElementById('reg-role');
const patientFields = document.getElementById('patient-fields');
const doctorFields = document.getElementById('doctor-fields');

function updateRoleFields(){
    const role = roleSelect.value;
    if(role === 'doctor'){
        doctorFields.style.display = 'block';
        patientFields.style.display = 'none';
    } else {
        doctorFields.style.display = 'none';
        patientFields.style.display = 'block';
    }
}

roleSelect.addEventListener('change', updateRoleFields);
updateRoleFields();

document.getElementById('register-btn').addEventListener('click', async () => {
    const first_name = document.getElementById('reg-first-name').value;
    const last_name = document.getElementById('reg-last-name').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const role = roleSelect.value;

    // use provided username (unique) if present, otherwise fall back to email
    const providedUsername = document.getElementById('reg-username') ? document.getElementById('reg-username').value : '';
    const username = providedUsername || email;
    const payload = { first_name, last_name, username, email, password, role };

    if(role === 'patient'){
        payload.phone = document.getElementById('reg-phone').value;
        payload.address = document.getElementById('reg-address').value;
        payload.date_of_birth = document.getElementById('reg-dob').value;
        payload.gender = document.getElementById('reg-gender').value;
        payload.blood_type = document.getElementById('reg-blood-type').value;
    } else if(role === 'doctor'){
        payload.specialization = document.getElementById('doc-specialization').value;
        payload.license_number = document.getElementById('doc-license').value;
        const feeVal = document.getElementById('doc-fee').value;
        payload.consultation_fee = feeVal ? Number(feeVal) : undefined;
        payload.phone = document.getElementById('doc-phone').value;
        const days = Array.from(document.querySelectorAll('.avail-day:checked')).map(el => el.value);
        payload.availability_days = days;
    }

    try{
        const res = await fetch('http://localhost:8000/register', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        const m = document.getElementById('reg-result');
        if(res.ok && data && data.user_id){
            // store token and user info so user is effectively logged in after registering
            if(data.access_token) localStorage.setItem('access_token', data.access_token);
            if(data.role) localStorage.setItem('role', data.role);
            if(data.user_id) localStorage.setItem('user_id', data.user_id);

            // If user registered as doctor, auto-create a doctor profile in doctor-service using the returned token
            if(role === 'doctor'){
                const docPayload = {
                    first_name,
                    last_name,
                    specialization: payload.specialization || '',
                    license_number: payload.license_number || '',
                    phone: payload.phone || '',
                    email: email,
                    consultation_fee: payload.consultation_fee || 100.0,
                    available_days: Array.isArray(payload.availability_days) ? payload.availability_days.join(',') : (payload.availability_days || '')
                };
                try{
                    // Create doctor profile without Authorization (unconditional public creation)
                    const r = await fetch('http://localhost:8002/doctors', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(docPayload)
                    });
                    const created = await r.json();
                    if(r.ok){
                        m.style.color = 'green';
                        m.innerText = 'Registration successful and doctor profile created. You are logged in.';
                        document.getElementById('reg-password').value = '';
                    } else {
                        m.style.color = '';
                        m.innerText = 'Registered but failed to create doctor profile: ' + (created.detail || JSON.stringify(created));
                    }
                } catch(e){
                    m.style.color = '';
                    m.innerText = 'Registered but error creating doctor profile: ' + e;
                }
            } else {
                m.style.color = 'green';
                m.innerText = 'Registration successful. You can sign in now.';
                document.getElementById('reg-password').value = '';
            }
        } else {
            m.style.color = '';
            m.innerText = 'Registration failed: ' + (data.detail || JSON.stringify(data));
        }
    } catch(err){
        const m = document.getElementById('reg-result');
        m.innerText = 'Error: ' + err;
    }
});
