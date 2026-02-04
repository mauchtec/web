// Interactive, professional people table for GateCore
// Requires: table with id 'peopleTable', tbody id 'peopleTableBody', and filterable-header ths

document.addEventListener('DOMContentLoaded', function() {
    // Extract table data from rendered HTML
    const table = document.getElementById('peopleTable');
    const tbody = document.getElementById('peopleTableBody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const columns = [
        'name', 'gender', 'id_number', 'phone', 'phone_device_type', 'phone_otp',
        'facial_recognition_enabled', 'email', 'date_of_birth', 'emergency_contact',
        'tags', 'unit', 'address'
    ];
    // Build data array for filtering
    const data = rows.map(row => {
        const cells = row.querySelectorAll('td');
        return {
            name: cells[0]?.textContent.trim() || '',
            gender: cells[1]?.textContent.trim() || '',
            id_number: cells[2]?.textContent.trim() || '',
            phone: cells[3]?.textContent.trim() || '',
            phone_device_type: cells[4]?.textContent.trim() || '',
            phone_otp: cells[5]?.textContent.trim() || '',
            facial_recognition_enabled: cells[6]?.textContent.trim() || '',
            email: cells[7]?.textContent.trim() || '',
            date_of_birth: cells[8]?.textContent.trim() || '',
            emergency_contact: cells[9]?.textContent.trim() || '',
            tags: cells[10]?.textContent.trim() || '',
            unit: cells[11]?.textContent.trim() || '',
            address: cells[12]?.textContent.trim() || '',
            actions: cells[13]?.innerHTML || ''
        };
    });
    // State
    let activeFilters = {};
    columns.forEach(col => activeFilters[col] = []);
    let globalSearchTerm = '';
    let activeDropdown = null;
    // Populate filter options
    function populateFilterOptions() {
        columns.forEach((col, idx) => {
            const optionsContainer = document.getElementById(col + '-options');
            if (!optionsContainer) return;
            // Unique values
            const unique = [...new Set(data.map(row => row[col]).filter(Boolean))];
            optionsContainer.innerHTML = '';
            unique.forEach(val => {
                const div = document.createElement('div');
                div.className = 'filter-option';
                div.innerHTML = `<input type="checkbox" id="${col}-${val}" value="${val}"><label for="${col}-${val}">${val}</label>`;
                optionsContainer.appendChild(div);
            });
            // Search inside dropdown
            const filterSearch = optionsContainer.parentElement.querySelector('.filter-search');
            filterSearch.addEventListener('input', function() {
                const term = this.value.toLowerCase();
                optionsContainer.querySelectorAll('.filter-option').forEach(opt => {
                    const label = opt.querySelector('label').textContent.toLowerCase();
                    opt.style.display = label.includes(term) ? 'flex' : 'none';
                });
            });
            // Apply/reset
            const applyBtn = optionsContainer.parentElement.querySelector('.apply-btn');
            const resetBtn = optionsContainer.parentElement.querySelector('.reset-btn');
            applyBtn.addEventListener('click', function() { applyColumnFilter(col); });
            resetBtn.addEventListener('click', function() { resetColumnFilter(col); });
        });
    }
    // Render table
    function renderTable(filtered) {
        tbody.innerHTML = '';
        if (!filtered.length) {
            document.getElementById('noResults').style.display = 'block';
        } else {
            document.getElementById('noResults').style.display = 'none';
            filtered.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${row.name}</td>
                    <td>${row.gender}</td>
                    <td>${row.id_number}</td>
                    <td>${row.phone}</td>
                    <td>${row.phone_device_type}</td>
                    <td>${row.phone_otp}</td>
                    <td>${row.facial_recognition_enabled}</td>
                    <td>${row.email}</td>
                    <td>${row.date_of_birth}</td>
                    <td>${row.emergency_contact}</td>
                    <td>${row.tags}</td>
                    <td>${row.unit}</td>
                    <td>${row.address}</td>
                    <td>${row.actions}</td>
                `;
                tbody.appendChild(tr);
            });
        }
        updateRecordCount(filtered.length);
    }
    // Filtering logic
    function filterTable() {
        let filtered = data;
        columns.forEach(col => {
            if (activeFilters[col].length) {
                filtered = filtered.filter(row => activeFilters[col].includes(row[col]));
            }
        });
        if (globalSearchTerm) {
            filtered = filtered.filter(row => Object.values(row).some(val => String(val).toLowerCase().includes(globalSearchTerm)));
        }
        renderTable(filtered);
    }
    // Dropdown logic
    function toggleFilterDropdown(col) {
        closeActiveDropdown();
        const header = document.querySelector(`.filterable-header[data-column="${col}"]`);
        const dropdown = header.querySelector('.filter-dropdown');
        header.classList.add('active');
        dropdown.classList.add('active');
        activeDropdown = col;
        // Pre-check
        dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = activeFilters[col].includes(cb.value);
        });
    }
    function closeActiveDropdown() {
        if (activeDropdown) {
            const header = document.querySelector(`.filterable-header[data-column="${activeDropdown}"]`);
            const dropdown = header.querySelector('.filter-dropdown');
            header.classList.remove('active');
            dropdown.classList.remove('active');
            activeDropdown = null;
        }
    }
    function applyColumnFilter(col) {
        const dropdown = document.querySelector(`.filterable-header[data-column="${col}"] .filter-dropdown`);
        const checked = dropdown.querySelectorAll('input[type="checkbox"]:checked');
        activeFilters[col] = Array.from(checked).map(cb => cb.value);
        closeActiveDropdown();
        filterTable();
    }
    function resetColumnFilter(col) {
        activeFilters[col] = [];
        const dropdown = document.querySelector(`.filterable-header[data-column="${col}"] .filter-dropdown`);
        dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
        dropdown.querySelector('.filter-search').value = '';
        dropdown.querySelectorAll('.filter-option').forEach(opt => opt.style.display = 'flex');
        filterTable();
    }
    function resetAllFilters() {
        columns.forEach(col => activeFilters[col] = []);
        document.getElementById('globalSearch').value = '';
        globalSearchTerm = '';
        document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
            dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            dropdown.querySelector('.filter-search').value = '';
            dropdown.querySelectorAll('.filter-option').forEach(opt => opt.style.display = 'flex');
        });
        closeActiveDropdown();
        filterTable();
    }
    // Global search
    document.getElementById('globalSearch').addEventListener('input', function() {
        globalSearchTerm = this.value.toLowerCase().trim();
        filterTable();
    });
    document.getElementById('resetAllFilters').addEventListener('click', resetAllFilters);
    document.querySelectorAll('.filterable-header').forEach(header => {
        header.addEventListener('click', function(e) {
            if (e.target.closest('.filter-dropdown')) return;
            const col = this.getAttribute('data-column');
            toggleFilterDropdown(col);
        });
    });
    document.addEventListener('click', function(e) {
        if (activeDropdown && !e.target.closest('.filter-dropdown') && !e.target.closest('.filterable-header.active')) {
            closeActiveDropdown();
        }
    });
    // Record count
    function updateRecordCount(visibleCount = null) {
        const totalCount = data.length;
        const visible = visibleCount !== null ? visibleCount : totalCount;
        document.getElementById('totalCount').textContent = totalCount;
        document.getElementById('visibleCount').textContent = visible;
    }
    // Emergency contact column is a combo of two fields
    // Already handled in data extraction
    // Initial render
    populateFilterOptions();
    renderTable(data);
    updateRecordCount();
});
