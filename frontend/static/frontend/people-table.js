// Interactive, professional people table for GateCore
// Requires: table with id 'peopleTable', tbody id 'peopleTableBody', and filterable-header ths


window.initPeopleTable = function() {
    // Extract table data from rendered HTML
    const table = document.getElementById('peopleTable');
    const tbody = document.getElementById('peopleTableBody');
    if (!table || !tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    // Detect columns from thead
    const ths = table.querySelectorAll('thead th');
    const columns = Array.from(ths)
        .map(th => th.getAttribute('data-column'))
        .filter(Boolean);
    // Build data array for filtering
    const data = rows.map(row => {
        const cells = row.querySelectorAll('td');
        let obj = { rowElement: row };
        columns.forEach((col, idx) => {
            obj[col] = cells[idx]?.textContent.trim() || '';
        });
        obj['actions'] = cells[cells.length - 1]?.innerHTML || '';
        return obj;
    });
    // State
    let activeFilters = {};
    columns.forEach(col => activeFilters[col] = []);
    let globalSearchTerm = '';
    let activeDropdown = null;
    // Populate filter options
    function populateFilterOptions() {
        columns.forEach((col, idx) => {
            const optionsContainer = document.getElementById(`people-${col}-options`);
            if (!optionsContainer) return;
            // Unique values
            const unique = [...new Set(data.map(row => row[col]).filter(Boolean))];
            optionsContainer.innerHTML = '';
            unique.forEach(val => {
                const div = document.createElement('div');
                div.className = 'filter-option';
                div.innerHTML = `<input type="checkbox" id="people-${col}-${val}" value="${val}"><label for="people-${col}-${val}">${val}</label>`;
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
            updateRecordCount(0);
            return;
        }
        document.getElementById('noResults').style.display = 'none';
        filtered.forEach(item => {
            tbody.appendChild(item.rowElement);
        });
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
        const header = document.querySelector(`#peopleTable .filterable-header[data-column="${col}"]`);
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
            const header = document.querySelector(`#peopleTable .filterable-header[data-column="${activeDropdown}"]`);
            const dropdown = header.querySelector('.filter-dropdown');
            header.classList.remove('active');
            dropdown.classList.remove('active');
            activeDropdown = null;
        }
    }
    function applyColumnFilter(col) {
        const dropdown = document.querySelector(`#peopleTable .filterable-header[data-column="${col}"] .filter-dropdown`);
        const checked = dropdown.querySelectorAll('input[type="checkbox"]:checked');
        activeFilters[col] = Array.from(checked).map(cb => cb.value);
        closeActiveDropdown();
        filterTable();
    }
    function resetColumnFilter(col) {
        activeFilters[col] = [];
        const dropdown = document.querySelector(`#peopleTable .filterable-header[data-column="${col}"] .filter-dropdown`);
        dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
        dropdown.querySelector('.filter-search').value = '';
        dropdown.querySelectorAll('.filter-option').forEach(opt => opt.style.display = 'flex');
        filterTable();
    }
    function resetAllFilters() {
        columns.forEach(col => activeFilters[col] = []);
        globalSearchTerm = '';
        document.querySelectorAll('#peopleTable .filter-dropdown').forEach(dropdown => {
            dropdown.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            dropdown.querySelector('.filter-search').value = '';
            dropdown.querySelectorAll('.filter-option').forEach(opt => opt.style.display = 'flex');
        });
        closeActiveDropdown();
        filterTable();
    }
    // No global search or resetAllFilters button in this page
    document.querySelectorAll('#peopleTable .filterable-header').forEach(header => {
        header.addEventListener('click', function(e) {
            e.stopPropagation();
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
    // Initial render
    populateFilterOptions();
    renderTable(data);
    updateRecordCount();
};
