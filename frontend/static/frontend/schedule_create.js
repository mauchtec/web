// Modal logic for schedule creation with API integration
document.addEventListener('DOMContentLoaded', function() {
	const modal = document.getElementById('scheduleModal');
	const openBtn = document.getElementById('openModalBtn');
	const closeBtn = document.getElementById('closeModalBtn');
	const cancelBtn = document.getElementById('cancelModalBtn');
	const form = document.getElementById('scheduleForm');
	const scheduleType = document.getElementById('scheduleType');
	const pinGroup = document.getElementById('pinGroup');
	const validUntilGroup = document.getElementById('validUntilGroup');
	const reason = document.getElementById('reason');
	const reasonOtherGroup = document.getElementById('reasonOtherGroup');
	const unitSelect = document.getElementById('unit');
	const residentSelect = document.getElementById('resident');
	const visitorSelect = document.getElementById('visitor');

	// Populate dropdowns from API
	async function populateDropdown(url, select, labelField, valueField) {
		try {
			const resp = await fetch(url);
			if (resp.ok) {
				const data = await resp.json();
				const items = data.results || [];
				select.innerHTML = '<option value="">Select</option>';
				items.forEach(item => {
					select.innerHTML += `<option value="${item[valueField]}">${item[labelField]}</option>`;
				});
			}
		} catch (err) {
			select.innerHTML = '<option value="">Select</option>';
		}
	}

	// Units
	populateDropdown('/api/gatecore/units/', unitSelect, 'unit_code', 'id');

	// Residents (people) filtered by unit using Occupancy
	unitSelect.onchange = async function() {
		const unitId = unitSelect.value;
		if (unitId) {
			try {
				// Fetch occupancies for the selected unit
				const resp = await fetch(`/api/gatecore/occupancies/?unit=${unitId}&is_active=true`);
				if (resp.ok) {
					const data = await resp.json();
					const items = data.results || [];
					residentSelect.innerHTML = '<option value="">Select</option>';
					// For each occupancy, fetch the person details
					for (const occ of items) {
						if (occ.person) {
							// If person is an object, use it directly; if it's an ID, fetch details
							let person = occ.person;
							if (typeof person === 'string' || typeof person === 'number') {
								// Fetch person details
								const presp = await fetch(`/api/gatecore/persons/${person}/`);
								if (presp.ok) {
									person = await presp.json();
								} else {
									continue;
								}
							}
							residentSelect.innerHTML += `<option value="${person.id}">${person.first_name} ${person.last_name || ''}</option>`;
						}
					}
				}
			} catch (err) {
				residentSelect.innerHTML = '<option value="">Select</option>';
			}
		} else {
			residentSelect.innerHTML = '<option value="">Select</option>';
		}
	};
	// Initial load: empty resident dropdown
	residentSelect.innerHTML = '<option value="">Select</option>';

	// Visitors (people) -- removed, no visitor dropdown in form

	// Show/hide days checkboxes based on days_allowed selection
	const daysAllowedSelect = document.getElementById('daysAllowed');
	const daysCheckboxes = document.getElementById('daysCheckboxes');
	if (daysAllowedSelect && daysCheckboxes) {
		daysAllowedSelect.onchange = function() {
			if (daysAllowedSelect.value === 'custom') {
				daysCheckboxes.style.display = '';
			} else {
				daysCheckboxes.style.display = 'none';
			}
		};
		// Initial state
		if (daysAllowedSelect.value === 'custom') {
			daysCheckboxes.style.display = '';
		} else {
			daysCheckboxes.style.display = 'none';
		}
	}

	// Ensure submit button is always visible
	const modalContent = document.querySelector('.modal-content');
	if (modalContent) {
		modalContent.style.overflowY = 'auto';
		modalContent.style.maxHeight = '90vh';
	}

	function openModal() {
		modal.style.display = 'block';
	}
	function closeModal() {
		modal.style.display = 'none';
		form.reset();
		pinGroup.style.display = 'none';
		validUntilGroup.style.display = '';
		reasonOtherGroup.style.display = 'none';
	}
	openBtn.onclick = openModal;
	closeBtn.onclick = closeModal;
	cancelBtn.onclick = closeModal;

	window.onclick = function(event) {
		if (event.target === modal) {
			closeModal();
		}
	};

	scheduleType.onchange = function() {
		if (scheduleType.value === 'preclearance') {
			pinGroup.style.display = '';
			validUntilGroup.style.display = 'none';
		} else {
			pinGroup.style.display = 'none';
			validUntilGroup.style.display = '';
		}
	};

	reason.onchange = function() {
		if (reason.value === 'other') {
			reasonOtherGroup.style.display = '';
		} else {
			reasonOtherGroup.style.display = 'none';
		}
	};

	form.onsubmit = async function(e) {
		e.preventDefault();
		// Validate start and end date
		const startDate = form.valid_from.value;
		const endDate = form.valid_until.value;
		if (endDate && startDate && endDate < startDate) {
			alert('End date cannot be before start date.');
			return;
		}
		// Compose a default name for the schedule rule (required by backend)
		let residentName = form.resident.options[form.resident.selectedIndex]?.text || '';
		let reasonText = form.reason.options[form.reason.selectedIndex]?.text || '';
		let scheduleName = residentName && reasonText ? `${residentName} - ${reasonText}` : residentName || reasonText || 'Schedule';
		// Use the unit UUID (dropdown value)
		const scheduleData = {
			name: scheduleName,
			unit: form.unit.value || null,
			visitor: form.resident.value || null,
			schedule_kind: scheduleType.value,
			schedule_type: 'custom', // default to custom, or map as needed
			start_time: '00:00',
			end_time: '23:59',
			reason: form.reason.value,
			reason_other: form.reason_other.value,
			visitor_full_name: form.visitor_full_name.value,
			visitor_email: form.visitor_email.value,
			visitor_mobile: form.visitor_mobile.value,
			valid_from: form.valid_from.value,
			valid_until: form.valid_until.value,
			days_allowed: form.days_allowed.value,
			monday: form.monday.checked,
			tuesday: form.tuesday.checked,
			wednesday: form.wednesday.checked,
			thursday: form.thursday.checked,
			friday: form.friday.checked,
			saturday: form.saturday.checked,
			sunday: form.sunday.checked,
			notes: form.notes.value,
			exclude_holidays: form.exclude_holidays.checked,
			notify_resident: form.notify_resident.checked,
			recur_type: form.recur_type.value,
			recur_until: form.recur_until.value,
			is_active: form.is_active.value === 'true'
		};
		// If preclearance, auto-expire in 24hrs
		if (scheduleType.value === 'preclearance') {
			const fromDate = new Date(form.valid_from.value);
			const untilDate = new Date(fromDate.getTime() + 24*60*60*1000);
			scheduleData.valid_until = untilDate.toISOString().slice(0,10);
		}
		// POST to API
		try {
			const response = await fetch('/api/gatecore/schedule-rules/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': getCookie('csrftoken')
				},
				body: JSON.stringify(scheduleData)
			});
			if (response.ok) {
				const newSchedule = await response.json();
				if (window.addScheduleToTable) {
					window.addScheduleToTable(newSchedule);
				}
				closeModal();
			} else {
				const error = await response.json();
				console.error(error);
				alert(JSON.stringify(error, null, 2));
			}
		} catch (err) {
			alert('Error connecting to API.');
		}
	};

	// Helper to get CSRF token
	function getCookie(name) {
		let cookieValue = null;
		if (document.cookie && document.cookie !== '') {
			const cookies = document.cookie.split(';');
			for (let i = 0; i < cookies.length; i++) {
				const cookie = cookies[i].trim();
				if (cookie.substring(0, name.length + 1) === (name + '=')) {
					cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
					break;
				}
			}
		}
		return cookieValue;
	}
});
