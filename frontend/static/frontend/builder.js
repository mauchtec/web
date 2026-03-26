let iconIndex = [];
let iconPickerStepIndex = null;
let iconPickerTarget = "step";
let iconIndexLoaded = false;
let workflowIconName = "";
let workflowIconPath = "";

function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
    return match ? decodeURIComponent(match[2]) : null;
}

function buildJsonHeaders() {
    const headers = { "Content-Type": "application/json" };
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
        headers["X-CSRFToken"] = csrfToken;
    }
    return headers;
}

async function loadIconIndex() {
    if (iconIndexLoaded) return;
    const res = await fetch("/static/frontend/flaticons/icon_index.json", { credentials: "same-origin" });
    if (!res.ok) {
        iconIndex = [];
        iconIndexLoaded = true;
        return;
    }
    iconIndex = await res.json();
    iconIndexLoaded = true;
}

function iconAssetUrl(path) {
    if (!path) return "";
    return `/static/frontend/${path}`;
}

const defaultIconByType = {
    id_card: { name: "id_card", path: "flaticons/16/id_card.png" },
    vehicle_card: { name: "enter_vehicle", path: "flaticons/16/enter_vehicle.png" },
    name_card: { name: "user_badge", path: "flaticons/16/user_badge.png" },
    phone_card: { name: "phone_call", path: "flaticons/16/phone_call.png" },
    company_card: { name: "enter-family", path: "flaticons/16/enter-family.png" },
    button_card: { name: "info-button", path: "flaticons/16/info-button.png" },
    residence_card: { name: "home_location", path: "flaticons/16/home_location.png" },
};

function applyDefaultIcon(step) {
    if (!step || !step.props) return;
    const hasIcon = step.props.icon_path || step.props.icon_name;
    if (hasIcon) return;
    const fallback = defaultIconByType[step.type];
    if (!fallback) return;
    step.props.icon_name = fallback.name;
    step.props.icon_path = fallback.path;
}

function openIconPicker(target) {
    iconPickerTarget = target;
    iconPickerStepIndex = typeof target === "number" ? target : null;
    loadIconIndex().then(() => {
        document.getElementById("iconPickerModal").style.display = "flex";
        renderIconPicker();
    });
}

function closeIconPicker() {
    document.getElementById("iconPickerModal").style.display = "none";
    iconPickerStepIndex = null;
}

function renderIconPicker() {
    const grid = document.getElementById("iconPickerGrid");
    const query = (document.getElementById("iconSearchInput").value || "").toLowerCase();
    if (!grid) return;
    grid.innerHTML = "";
    const filtered = iconIndex.filter(item => item.name.toLowerCase().includes(query)).slice(0, 320);
    filtered.forEach(item => {
        const row = document.createElement("div");
        row.className = "icon-row-item";
        row.innerHTML = `
            <span>${item.name}</span>
            <div class="icon-row-actions">
                <button class="icon-view-btn" type="button">View</button>
                <button class="icon-use-btn" type="button">Use</button>
            </div>
        `;
        row.querySelector(".icon-view-btn").onclick = () => openIconPreview(item);
        row.querySelector(".icon-use-btn").onclick = () => selectIconForStep(item);
        grid.appendChild(row);
    });
    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state">No icons match your search.</div>';
    }
}

function openIconPreview(item) {
    const modal = document.getElementById("iconPreviewModal");
    const title = document.getElementById("iconPreviewTitle");
    const image = document.getElementById("iconPreviewImage");
    const path = document.getElementById("iconPreviewPath");
    if (!modal || !title || !image || !path) return;
    title.textContent = item.name;
    image.src = iconAssetUrl(item.path);
    path.textContent = item.path;
    modal.style.display = "flex";
}

function closeIconPreview() {
    const modal = document.getElementById("iconPreviewModal");
    if (modal) modal.style.display = "none";
}

function selectIconForStep(item) {
    if (iconPickerTarget === "workflow") {
        workflowIconName = item.name;
        workflowIconPath = item.path;
        const nameInput = document.getElementById("workflowIconName");
        const pathInput = document.getElementById("workflowIconPath");
        if (nameInput) nameInput.value = item.name;
        if (pathInput) pathInput.value = item.path;
        updateWorkflowIconPreview(item.path, item.name);
        closeIconPicker();
        return;
    }
    if (iconPickerStepIndex === null) return;
    const step = workflowSteps[iconPickerStepIndex];
    if (!step || !step.props) return;
    step.props.icon_name = item.name;
    step.props.icon_path = item.path;
    const nameInput = document.querySelector(`#edit-form-${iconPickerStepIndex} input[name='icon_name']`);
    const pathInput = document.querySelector(`#edit-form-${iconPickerStepIndex} input[name='icon_path']`);
    if (nameInput) nameInput.value = item.name;
    if (pathInput) pathInput.value = item.path;
    updateIconPreview(iconPickerStepIndex, item.path, item.name);
    closeIconPicker();
    updatePreview();
}

function updateIconPreview(idx, iconPath, iconName) {
    const preview = document.getElementById(`icon-preview-${idx}`);
    if (!preview) return;
    if (!iconPath) {
        preview.innerHTML = '<span class="empty-state">No icon</span>';
        return;
    }
    preview.innerHTML = `<img src="${iconAssetUrl(iconPath)}" alt="${iconName || "icon"}">`;
}

function updateWorkflowIconPreview(iconPath, iconName) {
    const preview = document.getElementById("workflow-icon-preview");
    if (!preview) return;
    if (!iconPath) {
        preview.innerHTML = '<span class="empty-state">No icon</span>';
        return;
    }
    preview.innerHTML = `<img src="${iconAssetUrl(iconPath)}" alt="${iconName || "icon"}">`;
}

async function fetchComponents() {
    try {
        const res = await fetch("/api/v1/components/", { credentials: "same-origin" });
        if (!res.ok) {
            throw new Error(`Failed to load components (${res.status})`);
        }
        const data = await res.json();
        return Array.isArray(data.components) ? data.components : [];
    } catch (error) {
        setComponentStatus("Failed to load components. Check /api/v1/components/.", true);
        return [];
    }
}

function renderComponentList(components) {
    const list = document.getElementById("componentList");
    if (!list) return;
    list.innerHTML = "";
    if (!components.length) {
        list.innerHTML = '<div class="empty-state">No components available.</div>';
        setComponentStatus("No components returned from API.", true);
        return;
    }
    components.forEach(comp => {
        const item = document.createElement("div");
        item.className = "component-item";
        item.draggable = true;
        item.dataset.type = comp.type;
        item.innerHTML = `
            <span class="component-icon">${comp.icon}</span>
            <div class="component-item-body">
                <span class="component-label">${comp.label}</span>
                <button type="button" class="icon-view-btn component-preview-btn" onclick='openComponentPreview(${JSON.stringify(comp.label)}, ${JSON.stringify(comp.html_preview)})'>View</button>
            </div>
        `;
        item.addEventListener("dragstart", e => {
            e.dataTransfer.setData("componentType", comp.type);
            setTimeout(() => item.classList.add("dragging"), 0);
        });
        item.addEventListener("dragend", () => {
            item.classList.remove("dragging");
        });
        list.appendChild(item);
    });
    setComponentStatus("Fetched component types: " + components.map(c => c.type).join(", "));
}

function openComponentPreview(title, html) {
    const modal = document.getElementById("componentPreviewModal");
    const header = document.getElementById("componentPreviewTitle");
    const body = document.getElementById("componentPreviewBody");
    if (!modal || !header || !body) return;
    header.textContent = title;
    body.innerHTML = html;
    modal.style.display = "flex";
}

function closeComponentPreview() {
    const modal = document.getElementById("componentPreviewModal");
    if (modal) modal.style.display = "none";
}

let dropzone = null;
let workflowSteps = [];

function setComponentStatus(message, isError = false) {
    const debug = document.getElementById("componentDebug");
    if (!debug) return;
    debug.innerText = message;
    debug.style.color = isError ? "#dc2626" : "";
}

function initDropzone() {
    dropzone = document.getElementById("canvasDropzone");
    if (!dropzone) return;

    dropzone.addEventListener("dragover", e => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", async e => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        const type = e.dataTransfer.getData("componentType");
        const comp = (await fetchComponents()).find(c => c.type === type);
        if (comp) {
            const step = {
                id: `${type}_${Math.random().toString(36).substr(2, 6)}`,
                type: comp.type,
                props: Object.fromEntries(comp.fields.map(f => [f.name, f.default || ""])),
            };
            step.props.icon_name = step.props.icon_name || "";
            step.props.icon_path = step.props.icon_path || "";
            applyDefaultIcon(step);
            workflowSteps.push(step);
            renderCanvas();
            updatePreview();
        }
    });
}

function renderCanvas() {
    if (!dropzone) return;
    dropzone.innerHTML = "";
    workflowSteps.forEach((step, idx) => {
        applyDefaultIcon(step);
        const hasIcon = step.props && (step.props.icon_path || step.props.icon_name);
        const div = document.createElement("div");
        div.className = "canvas-step";
        div.innerHTML = `
            <div class="step-header">
                <div>
                    <div class="step-title">${step.type}</div>
                    <div class="step-meta">
                        <span class="meta-pill">Step ${idx + 1}</span>
                        <span class="meta-pill ${hasIcon ? "" : "missing"}">${hasIcon ? "Icon set" : "Icon missing"}</span>
                    </div>
                </div>
                <div class="step-actions">
                    <button onclick='moveStep(${idx}, -1)' ${idx === 0 ? "disabled" : ""} title="Move Up">&#8593;</button>
                    <button onclick='moveStep(${idx}, 1)' ${idx === workflowSteps.length - 1 ? "disabled" : ""} title="Move Down">&#8595;</button>
                    <button onclick='editStep(${idx})'>Edit</button>
                    <button class='remove-btn' onclick='removeStep(${idx})'>Remove</button>
                </div>
            </div>
            <div id="edit-form-${idx}" class="edit-form"></div>
        `;
        dropzone.appendChild(div);
    });
}

async function editStep(idx) {
    const step = workflowSteps[idx];
    const comp = (await fetchComponents()).find(c => c.type === step.type);
    if (!comp) return;
    applyDefaultIcon(step);
    const formDiv = document.getElementById(`edit-form-${idx}`);
    if (!formDiv) return;
    let formHtml = '<form class="component-form" onsubmit="return false;">';
    const iconName = step.props.icon_name || "";
    const iconPath = step.props.icon_path || "";
    formHtml += `
        <div class='icon-field'>
            <label class='field-label'>Icon (optional):</label>
            <div class='icon-row'>
                <div id='icon-preview-${idx}' class='icon-preview-box'></div>
                <div>
                    <input type='text' name='icon_name' value='${iconName}' placeholder='Select an icon' readonly class='icon-input'>
                    <input type='hidden' name='icon_path' value='${iconPath}'>
                    <div class='field-helper'>Defaults apply if no icon is selected.</div>
                </div>
                <button type='button' class='icon-select-btn' onclick='openIconPicker(${idx})'>Choose</button>
            </div>
            <span class='error-message'></span>
        </div>
    `;
    comp.fields.forEach(field => {
        const value = step.props[field.name] ?? "";
        formHtml += `<div class='form-group'>`;
        formHtml += `<label class='form-label'>${field.label}:</label><br>`;
        if (field.type === "text" || field.type === "number") {
            formHtml += `<input type='${field.type}' name='${field.name}' value='${value}' class='form-control' ${field.required ? "required" : ""}>`;
        } else if (field.type === "textarea") {
            formHtml += `<textarea name='${field.name}' class='form-control' ${field.required ? "required" : ""}>${value}</textarea>`;
        } else if (field.type === "select" && field.options) {
            formHtml += `<select name='${field.name}' class='form-control' ${field.required ? "required" : ""}>`;
            field.options.forEach(opt => {
                formHtml += `<option value='${opt}' ${value == opt ? "selected" : ""}>${opt}</option>`;
            });
            formHtml += `</select>`;
        } else if (field.type === "checkbox") {
            formHtml += `<input type='checkbox' name='${field.name}' ${value ? "checked" : ""} class='form-checkbox'>`;
        }
        formHtml += `<span class='error-message'></span>`;
        formHtml += `</div>`;
    });
    formHtml += `<div class='form-actions'>`;
    formHtml += `<button type='submit' class='btn-primary'>Save</button> `;
    formHtml += `<button type='button' class='btn-secondary' onclick='closeEditForm(${idx})'>Cancel</button>`;
    formHtml += `</div>`;
    formHtml += "</form>";
    formDiv.innerHTML = formHtml;
    formDiv.style.display = "block";
    updateIconPreview(idx, iconPath, iconName);
    formDiv.querySelector("form").onsubmit = function() {
        let valid = true;
        const iconNameInput = formDiv.querySelector("[name='icon_name']");
        const iconPathInput = formDiv.querySelector("[name='icon_path']");
        step.props.icon_name = iconNameInput.value;
        step.props.icon_path = iconPathInput.value;
        comp.fields.forEach(field => {
            let val;
            const input = formDiv.querySelector(`[name='${field.name}']`);
            const errorSpan = input.parentElement.querySelector(".error-message");
            if (field.type === "checkbox") {
                val = input.checked;
            } else {
                val = input.value;
                if (field.type === "number") val = Number(val);
            }
            if (field.required && (val === "" || val === null || (field.type === "number" && isNaN(val)))) {
                errorSpan.textContent = "Required";
                errorSpan.style.display = "inline";
                valid = false;
            } else {
                errorSpan.textContent = "";
                errorSpan.style.display = "none";
            }
            step.props[field.name] = val;
        });
        applyDefaultIcon(step);
        if (!valid) return false;
        formDiv.style.display = "none";
        renderCanvas();
        updatePreview();
    };
}

function closeEditForm(idx) {
    const formDiv = document.getElementById(`edit-form-${idx}`);
    if (formDiv) formDiv.style.display = "none";
}

function moveStep(idx, direction) {
    const newIndex = idx + direction;
    if (newIndex < 0 || newIndex >= workflowSteps.length) return;
    const temp = workflowSteps[idx];
    workflowSteps[idx] = workflowSteps[newIndex];
    workflowSteps[newIndex] = temp;
    renderCanvas();
    updatePreview();
}

function removeStep(idx) {
    workflowSteps.splice(idx, 1);
    renderCanvas();
    updatePreview();
}

async function updatePreview() {
    let components = null;
    if (Array.isArray(workflowSteps)) {
        components = workflowSteps;
    }
    if (!components || !Array.isArray(components)) {
        document.getElementById("livePreview").innerHTML = '<span class="preview-message">Invalid workflow definition.</span>';
        return;
    }
    const res = await fetch("/api/v1/preview/", {
        method: "POST",
        headers: buildJsonHeaders(),
        credentials: "same-origin",
        body: JSON.stringify({ components }),
    });
    if (!res.ok) {
        document.getElementById("livePreview").innerHTML = '<span class="preview-message preview-message--error">Preview failed.</span>';
        return;
    }
    let data = null;
    try {
        data = await res.json();
    } catch (e) {
        document.getElementById("livePreview").innerHTML = '<span class="preview-message preview-message--error">Preview response error.</span>';
        return;
    }
    if (!data || typeof data.html !== "string") {
        document.getElementById("livePreview").innerHTML = '<span class="preview-message preview-message--error">No preview available.</span>';
        return;
    }
    document.getElementById("livePreview").innerHTML = data.html;
}

let currentWorkflowId = null;
let currentWorkflowName = "";

async function saveWorkflow() {
    const iconSkip = ["text_display", "text_card", "button", "button_card"];
    const workflowIconError = document.getElementById("workflowIconError");
    if (!workflowIconName && !workflowIconPath) {
        if (workflowIconError) {
            workflowIconError.textContent = "Workflow icon required";
            workflowIconError.style.display = "inline";
        }
        return;
    }
    if (workflowIconError) {
        workflowIconError.textContent = "";
        workflowIconError.style.display = "none";
    }
    const missing = workflowSteps.filter(
        step => !iconSkip.includes(step.type) && !(step.props && (step.props.icon_path || step.props.icon_name))
    );
    if (missing.length > 0) {
        alert("Please select an icon for each step. Missing: " + missing.map(s => s.type).join(", "));
        return;
    }
    const definition = {
        steps: workflowSteps,
        icon_name: workflowIconName,
        icon_path: workflowIconPath,
    };
    let url, method, payload;
    if (currentWorkflowId) {
        url = `/api/v1/workflow/${currentWorkflowId}/`;
        method = "PUT";
        payload = {
            name: currentWorkflowName,
            definition: definition,
        };
    } else {
        const name = prompt("Enter workflow name:");
        if (!name) return;
        url = "/api/v1/save/";
        method = "POST";
        payload = {
            name: name,
            description: "",
            version: "1.0.0",
            status: "draft",
            definition: definition,
        };
    }
    const res = await fetch(url, {
        method: method,
        headers: buildJsonHeaders(),
        credentials: "same-origin",
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.id) {
        alert("Workflow saved! ID: " + data.id);
        window.location.hash = data.id;
        currentWorkflowId = data.id;
    } else {
        alert("Save failed: " + (data.error || "Unknown error"));
    }
}

async function loadWorkflow(id) {
    const res = await fetch(`/api/v1/workflow/${id}/`, { credentials: "same-origin" });
    if (!res.ok) {
        alert("Workflow not found.");
        return;
    }
    const data = await res.json();
    if (data.definition && data.definition.steps) {
        workflowSteps = data.definition.steps;
        workflowIconName = data.definition.icon_name || "";
        workflowIconPath = data.definition.icon_path || "";
        const nameInput = document.getElementById("workflowIconName");
        const pathInput = document.getElementById("workflowIconPath");
        if (nameInput) nameInput.value = workflowIconName;
        if (pathInput) pathInput.value = workflowIconPath;
        updateWorkflowIconPreview(workflowIconPath, workflowIconName);
        currentWorkflowId = data.id;
        currentWorkflowName = data.name;
        renderCanvas();
        updatePreview();
    }
}

if (window.location.hash.length > 1) {
    loadWorkflow(window.location.hash.substring(1));
}

let allComponents = [];

async function fetchAndRenderComponents() {
    allComponents = await fetchComponents();
    renderComponentList(allComponents);
}

function filterComponentList() {
    const search = document.getElementById("componentSearch").value.toLowerCase();
    const filtered = allComponents.filter(c =>
        c.label.toLowerCase().includes(search) ||
        (c.description && c.description.toLowerCase().includes(search))
    );
    renderComponentList(filtered);
}

function initBuilderPage() {
    initDropzone();
    fetchAndRenderComponents();
    const reloadBtn = document.getElementById("reloadComponentsBtn");
    reloadBtn?.addEventListener("click", function() {
        fetchAndRenderComponents();
    });
}

function toggleTheme() {
    const html = document.documentElement;
    if (html.getAttribute("data-theme") === "dark") {
        html.setAttribute("data-theme", "light");
        localStorage.setItem("theme", "light");
    } else {
        html.setAttribute("data-theme", "dark");
        localStorage.setItem("theme", "dark");
    }
}

(function() {
    const saved = localStorage.getItem("theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
})();

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBuilderPage);
} else {
    initBuilderPage();
}
