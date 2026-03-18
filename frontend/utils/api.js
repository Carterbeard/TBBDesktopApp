const API_URL = "http://127.0.0.1:5050";
//URL for the location of the API

//new token function using refresh token
async function refreshAccessToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;
    const response = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (response.ok) {
        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        return true;
    }
    return false;
}

// Returns a valid token, refreshing if needed. Returns null if unauthenticated.
async function getValidToken() {
    let token = localStorage.getItem('token');
    if (!token) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) return null;
        token = localStorage.getItem('token');
    }
    return token;
}

async function getMe() {
    const token = localStorage.getItem('token');
    let response = await fetch(`${API_URL}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.status === 401) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            const newToken = localStorage.getItem('token');
            response = await fetch(`${API_URL}/auth/me`, {
                headers: { 'Authorization': `Bearer ${newToken}` }
            });
        }
    }
    return response;
}

//login check
async function loginUser(email, password) {
    return await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
}

//register check
async function registerUser(email, password, full_name) {
    return await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name })
    });
}

//logout function to remove tokens
async function logoutUser() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
        const token = localStorage.getItem('token');
        await fetch(`${API_URL}/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
}

async function uploadFile(csvFile, datasetName, catchmentThreshold) {
    const token = await getValidToken();
    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('dataset_name', datasetName);
    formData.append('catchment_threshold_area', catchmentThreshold);
    return await fetch(`${API_URL}/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
    });
}

async function processFile(jobId) {
    const token = await getValidToken();
    return await fetch(`${API_URL}/process/${jobId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
    });
}

async function getStatus(jobId) {
    const token = await getValidToken();
    return await fetch(`${API_URL}/status/${jobId}`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` },
    });
}

async function getJobs(status,limit){
    const token = await getValidToken();
    return await fetch(`${API_URL}/jobs?status=${status}&limit=${limit}`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` },
    });
}
