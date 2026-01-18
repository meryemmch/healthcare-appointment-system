const API_URL = "http://localhost:8006";
document.getElementById("create-btn").onclick = createInvoice;
document.getElementById("refresh-btn").onclick = loadInvoices;
document.getElementById("filter-btn").onclick = filterInvoices;
document.getElementById("summary-btn").onclick = viewSummary;

// initialize token from localStorage
function init(){
    const tok = localStorage.getItem('access_token');
    const role = localStorage.getItem('role') || '';
    const uid = localStorage.getItem('user_id') || '';
    if(tok && document.getElementById('token') && !document.getElementById('token').value) document.getElementById('token').value = tok;
    // top-user header removed (no persistent signed-in line)
    // role-aware nav: only show compact patient nav
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

function createInvoice() {
    const patient_id = parseInt(document.getElementById("patient-id").value);
    const appointment_id = document.getElementById("appointment-id").value || null;
    const amount = parseFloat(document.getElementById("amount").value);
    const description = document.getElementById("description").value;
    const invoice_date = document.getElementById("invoice-date").value;
    const due_date = document.getElementById("due-date").value;
    const token = document.getElementById("token").value;

    const data = { patient_id, appointment_id, amount, description, invoice_date, due_date };

    fetch(`${API_URL}/invoices`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(resp => {
        alert("Invoice created successfully!");
        loadInvoices();
    })
    .catch(err => alert("Error: " + err));
}

function loadInvoices() {
    const token = document.getElementById("token").value;
    fetch(`${API_URL}/invoices/my`, {
        headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => renderInvoices(data));
}

function filterInvoices() {
    const status = document.getElementById("filter-status").value;
    const token = document.getElementById("token").value;

    let url = `${API_URL}/invoices/my`;
    if (status) url += `?status=${status}`;

    fetch(url, { headers: { "Authorization": `Bearer ${token}` } })
    .then(res => res.json())
    .then(data => renderInvoices(data));
}

function renderInvoices(invoices) {
    let html = "<table><tr><th>ID</th><th>Patient</th><th>Appointment</th><th>Amount</th><th>Description</th><th>Status</th><th>Invoice Date</th><th>Due Date</th><th>Paid Date</th></tr>";
    invoices.forEach(inv => {
        html += `<tr>
            <td>${inv.id}</td>
            <td>${inv.patient_id}</td>
            <td>${inv.appointment_id || ""}</td>
            <td>${inv.amount}</td>
            <td>${inv.description || ""}</td>
            <td>${inv.status}</td>
            <td>${inv.invoice_date}</td>
            <td>${inv.due_date}</td>
            <td>${inv.paid_date || ""}</td>
        </tr>`;
    });
    html += "</table>";
    document.getElementById("invoices-list").innerHTML = html;
}

function viewSummary() {
    const token = document.getElementById("token").value;

    fetch(`${API_URL}/invoices/stats/summary`, {
        headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
        let html = "<ul>";
        html += `<li>Pending Invoices: ${data.pending_invoices} | Amount: ${data.pending_amount}</li>`;
        html += `<li>Paid Invoices: ${data.paid_invoices} | Amount: ${data.paid_amount}</li>`;
        html += `<li>Total Amount: ${data.total_amount}</li>`;
        html += "</ul>";
        document.getElementById("billing-summary").innerHTML = html;
    });
}

// Initial load
if(document.getElementById("token").value) loadInvoices();
