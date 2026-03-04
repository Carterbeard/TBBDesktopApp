function toggleMenu() {
    document.querySelector(".sideMenu").classList.toggle("active");
    }

function switchTab(targetId) {
        document.querySelectorAll('.formPanel').forEach(p => p.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');
        document.querySelectorAll('.tabBtn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.target === targetId);
        });
        //Clear the error message when switching tabs
        document.getElementById('errorMsg').innerText = '';
        document.getElementById('errorMsg').className = '';
    }

    document.querySelectorAll('.tabBtn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.target));
    });

// fetches user from API (function getMe() in api.js) and shows profile
// clears storage and returns to auth page if token invalid
async function fetchAndShowProfile() {
    const response = await getMe();
    const data = await response.json();
    if (response.ok) {
        showProfile(data);
    } else {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        showAuth();
    }
}

//hides auth container and shows profile, populates name and email
function showProfile(data) {
    document.getElementById('authContainer').style.display = 'none';
    document.getElementById('profileContainer').style.display = 'block';
    document.getElementById('profileName').innerText = data.full_name || 'No name set';
    document.getElementById('profileEmail').innerText = data.email || '';
}

//hides profile and returns to auth
function showAuth() {
    document.getElementById('authContainer').style.display = '';
    document.getElementById('profileContainer').style.display = 'none';
}

//on page load, skip auth entirely if a token already exists
window.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (token) {
        fetchAndShowProfile();
    }
});

//calls logoutUser() from api.js then returns to auth
document.querySelector('.logoutBtn').addEventListener('click', async () => {
    await logoutUser();
    showAuth();
});


//login code
document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const response = await loginUser(
        document.getElementById('loginEmail').value,
        document.getElementById('loginPassword').value
    );
    const data = await response.json();
    if (response.ok) {
        //code 200
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        document.getElementById('errorMsg').classList.add('success');
        document.getElementById('errorMsg').innerText = "Login Successful!";
        setTimeout(() => {
            showProfile(data.user);
        }, 500);
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
    const response = await registerUser(
        document.getElementById('regEmail').value,
        document.getElementById('regPassword').value,
        document.getElementById('regName').value
    );
    const data = await response.json();
    if (response.ok) {
        //code 200
        document.getElementById('errorMsg').classList.add('success');
        document.getElementById('errorMsg').innerText = "You are now registered, please login.";
        setTimeout(()=>{
            switchTab('loginPanel');
        },1000);
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