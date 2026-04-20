let currentPage = 1;
const rowsPerPage = 10;
let currentRecords = [];
let performanceChartInstance = null;

const labelColors = {
    'Excellent': '#10b981', // green
    'Good': '#3b82f6', // blue
    'Average': '#f59e0b', // yellow
    'Needs Improvement': '#ef4444' // red
};

// Load data
async function loadData(page = 1) {
    currentPage = page;
    const searchInput = document.getElementById('searchInput');
    const subjectInput = document.getElementById('subjectInput');
    const resultInput = document.getElementById('resultInput');
    const semesterInput = document.getElementById('semesterInput');
    const dateFromInput = document.getElementById('dateFrom');
    const dateToInput = document.getElementById('dateTo');

    const params = new URLSearchParams({
        search: searchInput ? searchInput.value : '',
        subject: subjectInput ? subjectInput.value : '',
        result: resultInput ? resultInput.value : '',
        semester: semesterInput ? semesterInput.value : '',
        date_from: dateFromInput ? dateFromInput.value : '',
        date_to: dateToInput ? dateToInput.value : '',
        page: currentPage,
        limit: rowsPerPage
    });

    const response = await fetch(`/admin/data?${params}`);
    const data = await response.json();
    
    if (data.success) {
        currentRecords = data.records;
        updateStats(data);
        renderTable(data.records);
        renderPagination(data.page, data.total_pages);
    }
    
    // Load ALL data for the chart to be accurate
    const chartParams = new URLSearchParams({
        search: searchInput ? searchInput.value : '',
        subject: subjectInput ? subjectInput.value : '',
        result: resultInput ? resultInput.value : '',
        semester: semesterInput ? semesterInput.value : '',
        date_from: dateFromInput ? dateFromInput.value : '',
        date_to: dateToInput ? dateToInput.value : '',
        limit: 0 // fetch all for stats
    });
    const chartResponse = await fetch(`/admin/data?${chartParams}`);
    const chartData = await chartResponse.json();
    if (chartData.success) {
        updateChart(chartData.records);
    }
}

// Update basic stats
async function updateStats(data) {
    document.getElementById('adminEmail').textContent = data.admin_email || 'admin@school.com';
    document.getElementById('totalPredictions').textContent = data.total_predictions;
    
    try {
        const usersResponse = await fetch('/admin/users');
        const usersData = await usersResponse.json();
        if (usersData.success) {
            document.getElementById('totalUsers').textContent = usersData.users.length;
        }
    } catch (e) {
        console.error("Failed to load users", e);
    }
}

function updateChart(allRecords) {
    console.log("updateChart called with records: ", allRecords.length);
    const canvas = document.getElementById('performanceChart');
    if (!canvas) {
        console.error("Canvas element not found!");
        return;
    }
    const ctx = canvas.getContext('2d');
    
    // Destroy previous chart
    if (performanceChartInstance) {
        performanceChartInstance.destroy();
    }

    // Tally records
    const counts = { 'Excellent': 0, 'Good': 0, 'Average': 0, 'Needs Improvement': 0 };
    let hasData = false;

    allRecords.forEach(r => {
        if (counts[r.predicted_label] !== undefined) {
            counts[r.predicted_label]++;
            hasData = true;
        }
    });

    let chartLabels;
    let chartData;
    let chartColors;

    if (!hasData) {
        chartLabels = ['Waiting for predictions...'];
        chartData = [1];
        chartColors = ['#cbd5e1']; // light gray
    } else {
        chartLabels = ['Excellent', 'Good', 'Average', 'Needs Improvement'];
        chartData = [counts['Excellent'], counts['Good'], counts['Average'], counts['Needs Improvement']];
        chartColors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];
    }

    // Create fresh pie chart
    performanceChartInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartData,
                backgroundColor: chartColors,
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 15, 
                hoverBorderWidth: 0
            }]
        },
        options: {
            maintainAspectRatio: false,
            layout: {
                padding: 15 // Gives the slice room to pop out on hover!
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        usePointStyle: true,
                        font: { size: 14 }
                    }
                }
            },
            animation: {
                animateScale: true,
                animateRotate: true,
                duration: 1500,
                easing: 'easeInOutQuart'
            }
        }
    });
}

// Render table
function renderTable(records) {
    const tbody = document.getElementById('recordsBody');
    if (!records || records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="empty-state">No records found matching your filters.</td></tr>';
        return;
    }

    tbody.innerHTML = records.map((record, index) => {
        const animDelay = index * 0.05;
        // Format the database ID to be 3 digits minimum (e.g. 1 -> 001, 15 -> 015)
        const serialNo = "PR" + String(record.id).padStart(3, '0');
        
        return `
            <tr style="animation: fadeInUp 0.4s ease forwards ${animDelay}s; opacity: 0; transform: translateY(10px);">
                <td style="text-align: center; font-weight: bold; color: #64748b;">${serialNo}</td>
                <td style="font-weight: 600;">${record.user_name || '<span style="color: #94a3b8; font-style: italic;">Guest</span>'}</td>
                <td style="font-weight: 600;">${record.student_name}</td>
                <td><span style="background: #f1f5f9; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #4338ca;">${record.semester || 'SEM II'}</span></td>
                <td><span style="background: #f8fafc; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #475569;">${record.subject || 'General'}</span></td>
                <td>${Math.round(record.attendance)}%</td>
                <td>${Math.round(record.mid_marks)}</td>
                <td>${Math.round(record.assignments)}</td>
                <td>${Math.round(record.study_hours)}h</td>
                <td><span class="status-chip" style="background: ${labelColors[record.predicted_label]}20; color: ${labelColors[record.predicted_label]};">${record.predicted_label}</span></td>
                <td style="color: #64748b; font-size: 13px;">${formatDate(record.created_at)}</td>
                <td style="text-align: center; white-space: nowrap;">
                    <button onclick="openEditModal(${record.id})" class="btn btn-sm btn-outline-primary me-1" title="Edit Record" style="border-radius: 8px; padding: 4px 8px;">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="deletePrediction(${record.id}, '${serialNo}')" class="btn btn-sm btn-outline-danger" title="Delete Record" style="border-radius: 8px; padding: 4px 8px;">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderPagination(current, total) {
    const container = document.getElementById('pagination');
    if (total <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '';
    
    // Prev
    if (current > 1) {
        html += `<button class="page-btn" onclick="loadData(${current - 1})"><i class="fas fa-chevron-left"></i></button>`;
    }

    // Pages
    for (let i = 1; i <= total; i++) {
        if (i === 1 || i === total || (i >= current - 1 && i <= current + 1)) {
            html += `<button class="page-btn ${i === current ? 'active' : ''}" onclick="loadData(${i})">${i}</button>`;
        } else if (i === current - 2 || i === current + 2) {
            html += `<span style="padding: 8px; color: #64748b;">...</span>`;
        }
    }

    // Next
    if (current < total) {
        html += `<button class="page-btn" onclick="loadData(${current + 1})"><i class="fas fa-chevron-right"></i></button>`;
    }

    container.innerHTML = html;
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    loadData();

    ['searchInput', 'subjectInput', 'resultInput', 'semesterInput'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', debounce(() => loadData(1), 400));
        if (el && el.tagName === 'SELECT') {
            el.addEventListener('change', () => loadData(1));
        }
    });
    
    ['dateFrom', 'dateTo'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => loadData(1));
    });

    document.getElementById('logoutBtn')?.addEventListener('click', async () => {
        const res = await fetch('/logout', { method: 'POST' });
        if (res.ok) window.location.href = '/';
    });

    document.getElementById('exportBtn')?.addEventListener('click', () => {
        const params = new URLSearchParams({
            search: document.getElementById('searchInput')?.value || '',
            subject: document.getElementById('subjectInput')?.value || '',
            serial: document.getElementById('serialInput')?.value || '',
            result: document.getElementById('resultInput')?.value || '',
            semester: document.getElementById('semesterInput')?.value || '',
            date_from: document.getElementById('dateFrom')?.value || '',
            date_to: document.getElementById('dateTo')?.value || '',
        });
        window.location.href = `/admin/export?${params}`;
    });

    const body = document.body;
    const darkModeToggle = document.getElementById('darkModeToggle');
    
    // Check saved preference
    if (localStorage.getItem('adminDarkMode') === 'true') {
        body.classList.add('dark-mode');
        if (darkModeToggle) darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }

    darkModeToggle?.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        const isDark = body.classList.contains('dark-mode');
        localStorage.setItem('adminDarkMode', isDark);
        if (darkModeToggle) darkModeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
        
        // Update chart colors if exists
        if (performanceChartInstance) {
            Chart.defaults.color = isDark ? '#e2e8f0' : '#64748b';
            performanceChartInstance.update();
        }
    });
    
    Chart.defaults.color = body.classList.contains('dark-mode') ? '#e2e8f0' : '#64748b';
    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

    // Setup Semester -> Subject dynamic filtering for Search
    const semesterInput = document.getElementById('semesterInput');
    const subjectInput = document.getElementById('subjectInput');
    
    if (semesterInput && subjectInput) {
        // Store original optgroups
        const originalOptgroups = Array.from(subjectInput.querySelectorAll('optgroup'));
        
        semesterInput.addEventListener('change', () => {
            const selectedSem = semesterInput.value;
            
            // Clear current selection if it's not "All Subjects"
            if (subjectInput.value !== "") {
                subjectInput.value = "";
            }

            // Remove all current optgroups
            subjectInput.querySelectorAll('optgroup').forEach(og => og.remove());

            if (!selectedSem) {
                subjectInput.options[0].textContent = "All Subjects";
            } else {
                subjectInput.options[0].textContent = "All Subjects";
                const semText = selectedSem.split(' ')[1]; // "I", "II", etc.
                
                originalOptgroups.forEach(og => {
                    const label = og.getAttribute('label');
                    if (label.endsWith(' ' + semText)) {
                        subjectInput.appendChild(og.cloneNode(true));
                    }
                });
            }
            loadData(1);
        });

        // Initial state
        if (!semesterInput.value) {
            subjectInput.querySelectorAll('optgroup').forEach(og => og.remove());
            subjectInput.options[0].textContent = "All Subjects";
        } else {
            semesterInput.dispatchEvent(new Event('change'));
        }
    }

    // Alert user if click Subject without Semester
    if (subjectInput && semesterInput) {
        subjectInput.addEventListener('mousedown', (e) => {
            if (!semesterInput.value) {
                e.preventDefault();
                alert("Please select a Semester first to view relevant subjects.");
                semesterInput.focus();
            }
        });
    }

    // Dynamic filtering for Edit Modal
    const editSemester = document.getElementById('editSemester');
    const editSubject = document.getElementById('editSubject');

    if (editSemester && editSubject) {
        editSemester.addEventListener('change', () => {
            const selectedSem = editSemester.value;
            const optgroups = editSubject.querySelectorAll('optgroup');

            optgroups.forEach(og => {
                const label = og.getAttribute('label');
                if (label.includes(selectedSem.split(' ')[1])) {
                    og.style.display = '';
                } else {
                    og.style.display = 'none';
                }
            });
        });
    }

    // Setup Edit Save Listener
    document.getElementById('editForm')?.addEventListener('submit', (e) => {
        e.preventDefault();
        saveEdit();
    });
});

// Utils
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    // SQLite CURRENT_TIMESTAMP is in UTC but formatted as "YYYY-MM-DD HH:MM:SS"
    // By replacing space with T and adding Z, we force the browser to treat it as UTC timezone.
    let formattedStr = dateStr;
    if (!formattedStr.includes('T') && !formattedStr.includes('Z')) {
        formattedStr = formattedStr.replace(' ', 'T') + 'Z';
    }
    const date = new Date(formattedStr);
    return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
}

function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

async function deletePrediction(id, serialNo) {
    if (!confirm("Are you sure to delete record?")) {
        return;
    }
    try {
        const response = await fetch(`/admin/delete_prediction/${id}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            loadData(currentPage);
        } else {
            alert(data.message || 'Failed to delete record.');
        }
    } catch (e) {
        console.error("Deletion error:", e);
        alert('An error occurred while deleting the record.');
    }
}

function openEditModal(id) {
    const record = currentRecords.find(r => r.id === id);
    if (!record) return;

    document.getElementById('editId').value = record.id;
    document.getElementById('editStudentName').value = record.student_name;
    document.getElementById('editSemester').value = record.semester || 'SEM I';
    document.getElementById('editSemester').dispatchEvent(new Event('change'));
    document.getElementById('editSubject').value = record.subject || '';
    document.getElementById('editAttendance').value = record.attendance;
    document.getElementById('editMidMarks').value = record.mid_marks;
    document.getElementById('editAssignments').value = record.assignments;
    document.getElementById('editStudyHours').value = record.study_hours;

    const modal = new bootstrap.Modal(document.getElementById('editModal'));
    modal.show();
}

async function saveEdit() {
    const id = document.getElementById('editId').value;
    const payload = {
        student_name: document.getElementById('editStudentName').value,
        semester: document.getElementById('editSemester').value,
        subject: document.getElementById('editSubject').value,
        attendance: document.getElementById('editAttendance').value,
        mid_marks: document.getElementById('editMidMarks').value,
        assignments: document.getElementById('editAssignments').value,
        study_hours: document.getElementById('editStudyHours').value
    };

    try {
        const response = await fetch(`/admin/update_prediction/${id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (data.success) {
            const modalEl = document.getElementById('editModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            
            loadData(currentPage);
        } else {
            alert(data.message || 'Failed to update record.');
        }
    } catch (e) {
        console.error("Update error:", e);
        alert('An error occurred while updating the record.');
    }
}
