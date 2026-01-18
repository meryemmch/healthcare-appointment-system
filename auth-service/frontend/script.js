let token = "";

document.getElementById("login-btn").onclick = login;
document.getElementById("verify-btn").onclick = verifyToken;
document.getElementById("logout-btn").onclick = logout;

function login() {
    // the field now collects email; backend accepts email or username
    const username = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    fetch("http://localhost:8000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    })
    .then(res => res.json())
    .then(data => {
        if(data.access_token){
            token = data.access_token;
            // persist token + role
            localStorage.setItem('access_token', data.access_token);
            if(data.role) localStorage.setItem('role', data.role);
            if(data.user_id) localStorage.setItem('user_id', data.user_id);
            // redirect based on role: doctors -> doctor service, patients -> appointment service
            if(data.role === 'doctor'){
                window.location.href = 'http://localhost:8002/';
            } else {
                window.location.href = 'http://localhost:8003/';
            }
        } else {
            alert("Invalid credentials");
        }
    })
    .catch(err => alert("Error: " + err));
}

function showUserSection(data) {
    document.getElementById("auth-section").classList.add("hidden");
    document.getElementById("user-section").classList.remove("hidden");
    document.getElementById("user-info").innerHTML = `ID: ${data.user_id}, Role: ${data.role} <button id="copy-token" style="margin-left:8px;">Copy Token</button>`;
    document.getElementById("copy-token").onclick = copyToken;
    document.getElementById("verify-result").innerText = "";
}

function copyToken(){
    const b = `Bearer ${token}`;
    if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(b).then(()=> alert('Token copied to clipboard'))
    } else {
        // fallback
        const ta = document.createElement('textarea'); ta.value = b; document.body.appendChild(ta); ta.select(); try{ document.execCommand('copy'); alert('Token copied to clipboard') } catch(e){ alert('Copy failed') } ta.remove();
    }
}

function logout() {
    token = "";
    document.getElementById("auth-section").classList.remove("hidden");
    document.getElementById("user-section").classList.add("hidden");
    document.getElementById("user-info").innerText = "";
    document.getElementById("verify-result").innerText = "";
}

function verifyToken() {
    fetch("http://localhost:8000/verify", {
        headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
        if(data.valid){
            document.getElementById("verify-result").innerText = "Token is valid!";
        } else {
            document.getElementById("verify-result").innerText = "Token invalid!";
        }
    })
    .catch(err => alert("Error: " + err));
}
