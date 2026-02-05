// Table logic for displaying schedules from API
let schedules = [];


async function renderScheduleTable() {



	const container = document.getElementById('scheduleTableContainer');
	if (!container) return;

	let html = '';
	html += '<table id="scheduleTable" class="schedule-table" style="width:100%;border-collapse:collapse;">';
	html += '<thead><tr>';
	html += '<th>Resident</th>';
	html += '<th>Unit</th>';
	html += '<th>Valid From</th>';
	html += '<th>Valid Until</th>';
	html += '<th>Days</th>';
	html += '<th>Visitor Name</th>';
	html += '<th>Visitor Email</th>';
	html += '<th>Visitor Mobile</th>';
	html += '<th>PIN</th>';
	html += '<th>Actions</th>';
	html += '</tr></thead><tbody>';

	if (schedules.length === 0) {
		html += '<tr><td colspan="9" style="text-align:center;color:#64748b;">No schedules found.</td></tr>';
	} else {
		for (const sch of schedules) {
			let days = [];
			if (sch.days_allowed === 'weekdays') {
				days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
			}
			let unitName = sch.unit_name || '';
			let unitId = sch.unit;
			if (!unitName && unitId) {
				try {
					const unitResp = await fetch(`/api/gatecore/units/${unitId}/`);
					if (unitResp.ok) {
						const unitData = await unitResp.json();
						unitName = unitData.unit_code || unitData.text || unitId;
					}
				} catch {}
			}

			// Fetch resident details if not present
			let residentName = sch.resident_name || '';
			let residentId = sch.visitor; // visitor is the resident/person field
			if (!residentName && residentId) {
				try {
					const personResp = await fetch(`/api/gatecore/persons/${residentId}/`);
					if (personResp.ok) {
						const personData = await personResp.json();
						residentName = personData.full_name || `${personData.first_name} ${personData.last_name}`;
					}
				} catch {}
			}

				html += `<tr>
					<td>${residentName}</td>
					<td>${unitName}</td>
					<td>${sch.valid_from || ''}</td>
					<td>${sch.valid_until || ''}</td>
					<td>${days.join(', ')}</td>
					<td>${sch.visitor_full_name || ''}</td>
					<td>${sch.visitor_email || ''}</td>
					<td>${sch.visitor_mobile || ''}</td>
					<td>${sch.pin || ''}</td>
					<td><a href="#" class="action-link delete-btn" data-id="${sch.id}"><i class="fa fa-trash"></i> Delete</a></td>
					<td><a href="#" class="action-link delete-btn" data-id="${sch.id}"><i class="fa fa-trash"></i> Delete</a></td>
				</tr>`;
		}
	}
	html += '</tbody></table>';
	container.innerHTML = html;
	// Attach delete handlers
	container.querySelectorAll('.delete-btn').forEach(btn => {
		btn.onclick = async function() {
			const id = btn.getAttribute('data-id');
			try {
				const resp = await fetch(`/api/gatecore/schedule-rules/${id}/`, {
					method: 'DELETE',
					headers: {
						'X-CSRFToken': getCookie('csrftoken')
					}
				});
				if (resp.ok) {
					schedules = schedules.filter(s => s.id != id);
					renderScheduleTable();
				} else {
					alert('Failed to delete schedule.');
				}
			} catch (err) {
				alert('Error connecting to API.');
			}
		};
	});
}

window.addScheduleToTable = function(data) {
	schedules.push(data);
	renderScheduleTable();
};

async function fetchSchedules() {
	try {
		const resp = await fetch('/api/gatecore/schedule-rules/');
		if (resp.ok) {
			const data = await resp.json();
			schedules = data.results || [];
			await renderScheduleTable();
		}
	} catch (err) {
		// Optionally show error
	}
}
document.addEventListener('DOMContentLoaded', fetchSchedules);
