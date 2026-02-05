$(document).ready(function() {
    loadSchedules();

    // Open modal for add
    $('#add-schedule-btn').click(function() {
        clearForm();
        $('#scheduleModalLabel').text('Add Schedule Rule');
        $('#scheduleModal').modal('show');
    });

    // Submit form (add/edit)
    $('#schedule-form').submit(function(e) {
        e.preventDefault();
        const id = $('#schedule-id').val();
        const data = {
            name: $('#schedule-name').val(),
            schedule_type: $('#schedule-type').val(),
            is_active: $('#schedule-active').is(':checked')
        };
        const method = id ? 'PUT' : 'POST';
        const url = id ? `/api/schedule-rules/${id}/` : '/api/schedule-rules/';
        $('#schedule-form button[type="submit"]').prop('disabled', true).text('Saving...');
        $.ajax({
            url: url,
            type: method,
            data: JSON.stringify(data),
            contentType: 'application/json',
            success: function() {
                $('#scheduleModal').modal('hide');
                loadSchedules();
                showAlert(id ? 'Schedule rule updated.' : 'Schedule rule created.');
            },
            error: function(xhr) {
                let msg = 'Error saving schedule rule.';
                if (xhr.responseJSON && xhr.responseJSON.detail) msg = xhr.responseJSON.detail;
                showAlert(msg, 'danger');
            },
            complete: function() {
                $('#schedule-form button[type="submit"]').prop('disabled', false).text('Save');
            }
        });
    });

    // Edit button
    $('#schedule-table').on('click', '.edit-btn', function() {
        const id = $(this).data('id');
        $('#loading-spinner').show();
        $.get(`/api/schedule-rules/${id}/`, function(rule) {
            $('#schedule-id').val(rule.id);
            $('#schedule-name').val(rule.name);
            $('#schedule-type').val(rule.schedule_type);
            $('#schedule-active').prop('checked', rule.is_active);
            $('#scheduleModalLabel').text('Edit Schedule Rule');
            $('#scheduleModal').modal('show');
            $('#loading-spinner').hide();
        }).fail(function() {
            $('#loading-spinner').hide();
            showAlert('Failed to load schedule rule.', 'danger');
        });
    });

    // Delete button
    $('#schedule-table').on('click', '.delete-btn', function() {
        const id = $(this).data('id');
        if (confirm('Delete this schedule rule?')) {
            $.ajax({
                url: `/api/schedule-rules/${id}/`,
                type: 'DELETE',
                success: function() {
                    loadSchedules();
                    showAlert('Schedule rule deleted.', 'warning');
                },
                error: function() {
                    showAlert('Failed to delete schedule rule.', 'danger');
                }
            });
        }
    });

    function showAlert(message, type = 'success') {
        $('#alert-area').html(`<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`);
        setTimeout(() => { $('.alert').alert('close'); }, 3500);
    }

    function loadSchedules() {
        $('#loading-spinner').show();
        // Hardcoded dummy data for UI preview
        const data = [
            {id: 1, name: 'Main Gate 24/7', schedule_type: '24x7', is_active: true},
            {id: 2, name: 'Office Hours', schedule_type: 'business_hours', is_active: true},
            {id: 3, name: 'Weekend Only', schedule_type: 'weekends', is_active: false},
            {id: 4, name: 'Custom Night Shift', schedule_type: 'custom', is_active: true},
            {id: 5, name: 'Maintenance Window', schedule_type: 'custom', is_active: false}
        ];
        const tbody = $('#schedule-table tbody');
        tbody.empty();
        data.forEach(function(rule) {
            tbody.append(`
                <tr data-id="${rule.id}">
                    <td>${rule.name}</td>
                    <td>${rule.schedule_type}</td>
                    <td><span class="badge ${rule.is_active ? 'bg-success' : 'bg-secondary'}">${rule.is_active ? 'Yes' : 'No'}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary edit-btn me-1" data-id="${rule.id}" title="Edit"><i class="bi bi-pencil"></i></button>
                        <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${rule.id}" title="Delete"><i class="bi bi-trash"></i></button>
                    </td>
                </tr>
            `);
        });
        $('#loading-spinner').hide();
        // Uncomment below to use real API
        // $.get('/api/schedule-rules/', function(data) { ... });
    }

    function clearForm() {
        $('#schedule-id').val('');
        $('#schedule-name').val('');
        $('#schedule-type').val('');
        $('#schedule-active').prop('checked', false);
    }
});
