// Interactive table filtering for GateCore People
// Requires: table with id 'people-table', each th with class 'filterable', and a dropdown filter UI

document.addEventListener('DOMContentLoaded', function() {
    // Add dropdown filter to each filterable header
    document.querySelectorAll('#people-table th.filterable').forEach(function(th, idx) {
        const field = th.dataset.field;
        if (!field) return;
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Filter...';
        input.style = 'width: 90px; font-size: 0.95em; margin-top: 2px;';
        input.addEventListener('input', function() {
            filterTable(idx, input.value.toLowerCase());
        });
        th.appendChild(document.createElement('br'));
        th.appendChild(input);
    });

    function filterTable(colIdx, filterValue) {
        const table = document.getElementById('people-table');
        Array.from(table.tBodies[0].rows).forEach(function(row) {
            const cell = row.cells[colIdx];
            if (!cell) return;
            const text = cell.textContent.toLowerCase();
            row.style.display = text.includes(filterValue) ? '' : 'none';
        });
    }
});
