function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

function switchTab(targetId) {
        document.querySelectorAll('.form-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.target === targetId);
        });
        //Clear the error message when switching tabs
        document.getElementById('errorMsg').innerText = '';
        document.getElementById('errorMsg').className = '';
    }

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.target));
    });



const API_URL = "http://127.0.0.1:5050";
//URL for the location of the API

//login code
document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email: document.getElementById('loginEmail').value,
            password: document.getElementById('loginPassword').value
        })
    });
    const data = await response.json();
    if (response.ok) {
        //code 200
        localStorage.setItem('token', data.access_token);
        document.getElementById('errorMsg').classList.add('success');
        document.getElementById('errorMsg').innerText = "Login Successful!";
    } else {
        document.getElementById('errorMsg').classList.remove('success');
        if(response.status === 401){
            //Wrong password or email not found
            document.getElementById('errorMsg').innerText = "Invalid Email or Password";
        }
        else if (response.status === 422 && Array.isArray(data.detail)) {
            //422 -> Validation Error
            //loops through array of error messages
            //eg: [{ "msg": "field required", "loc": ["body", "email"] }]
            const errorMessages = data.detail.map(err => {
                // loc -> tells you which field failed 
                // msg -> tells you why the field failed
                if(err.type === "string_too_short"){
                    return "Password must be at least 8 characters.";
                }
                const field = err.loc[err.loc.length - 1]; 
                return `${field}: ${err.msg}`;
            });
            if (errorMessages.length === 1 && errorMessages[0] === "Password must be at least 8 characters.") {
                document.getElementById('errorMsg').innerText = errorMessages[0];
            } else {
                document.getElementById('errorMsg').innerText = "Validation Errors (422): " + errorMessages.join(", ");
            }
        } else {
            document.getElementById('errorMsg').innerText = "Error: " + data.detail;
        }
    }
};

//register code
document.getElementById('regForm').onsubmit = async (e) => {
    e.preventDefault();
    const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email: document.getElementById('regEmail').value,
            password: document.getElementById('regPassword').value,
            full_name: document.getElementById('regName').value
        })
    });
    const data = await response.json();
    if (response.ok) {
        //code 200
        document.getElementById('errorMsg').classList.add('success');
        document.getElementById('errorMsg').innerText = "You are now registered, please login.";
    } else {
        document.getElementById('errorMsg').classList.remove('success');
        if(response.status === 400){
            document.getElementById('errorMsg').innerText = "Email already exists.";
        } else if (response.status === 422 && Array.isArray(data.detail)) {
            //422 -> Validation Error
            //loops through array of error messages
            //eg: [{ "msg": "field required", "loc": ["body", "email"] }]
            const errorMessages = data.detail.map(err => {
                // loc -> tells you which field failed 
                // msg -> tells you why the field failed
                if(err.type === "string_too_short"){
                    return "Password must be at least 8 characters.";
                }
                const field = err.loc[err.loc.length - 1]; 
                return `${field}: ${err.msg}`;
            });
            document.getElementById('errorMsg').innerText = "Validation Errors: (error code 422)" + errorMessages.join(", ");
        } else {
            document.getElementById('errorMsg').innerText = "Error: " + data.detail;
        }
    }
};