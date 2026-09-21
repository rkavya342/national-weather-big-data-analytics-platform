/**
 * National Weather Event Monitoring & Alert Center Controller
 * Handles real-time SocketIO events, Leaflet map markers, Chart.js analytics,
 * multi-criteria filters, alert details modal, and admin resolution.
 */

document.addEventListener("DOMContentLoaded", function () {
    let currentPage = 1;
    let totalPages = 1;

    // Leaflet map and marker layer group
    let alertMap = null;
    let mapMarkersGroup = null;

    // Chart.js instances
    let chartSeverity = null;
    let chartEvents = null;
    let chartStates = null;

    // Current selected alert ID for resolution
    let currentModalAlertId = null;

    // 1. Initialize Leaflet Map
    function initAlertMap() {
        const mapContainer = document.getElementById("alert-map");
        if (!mapContainer) return;

        alertMap = L.map("alert-map").setView([20.5937, 78.9629], 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 18
        }).addTo(alertMap);

        mapMarkersGroup = L.layerGroup().addTo(alertMap);
    }

    // Custom Map Marker Color Helper
    function getMarkerIcon(severity, status) {
        let color = "#198754"; // default green
        if (status === "Active") {
            if (severity === "HIGH") color = "#dc3545"; // red
            else if (severity === "MEDIUM") color = "#fd7e14"; // orange
            else color = "#ffc107"; // yellow
        }

        const svgMarker = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}" width="32" height="32" style="filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.4));">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
        `;

        return L.divIcon({
            className: "custom-leaflet-marker",
            html: svgMarker,
            iconSize: [32, 32],
            iconAnchor: [16, 32],
            popupAnchor: [0, -30]
        });
    }

    // 2. Socket.IO Connection & Toast Notifications
    function initSocketIO() {
        if (typeof io === "undefined") return;

        const socket = io();

        const badge = document.getElementById("live-connection-badge");
        socket.on("connect", function () {
            if (badge) {
                badge.className = "badge bg-success rounded-pill px-3 py-2 ms-2";
                badge.innerHTML = '<i class="bi bi-circle-fill me-1 text-white" style="font-size: 0.65rem;"></i> Live Connection: Connected';
            }
        });

        socket.on("disconnect", function () {
            if (badge) {
                badge.className = "badge bg-secondary rounded-pill px-3 py-2 ms-2";
                badge.innerHTML = '<i class="bi bi-circle-fill me-1 text-danger" style="font-size: 0.65rem;"></i> Live Connection: Disconnected';
            }
        });

        // Listen for real-time weather alerts
        socket.on("weather_alert", function (alertData) {
            console.log("Real-time weather alert received:", alertData);
            showToastAlert(alertData);
            loadAlertsData(currentPage);
        });

        socket.on("weather_update", function () {
            loadAlertsData(currentPage);
        });
    }

    // Toast Alert Notification Banner
    function showToastAlert(alertData) {
        const toastContainer = document.getElementById("toast-container");
        if (!toastContainer) return;

        const severity = alertData.severity || "HIGH";
        const city = alertData.city || "Unknown City";
        const eventType = alertData.event_type || "Weather Event";

        let bgClass = "bg-danger text-white";
        if (severity === "MEDIUM") bgClass = "bg-warning text-dark";
        else if (severity === "LOW") bgClass = "bg-info text-dark";

        const toastId = `toast-${Date.now()}`;
        const toastHtml = `
            <div id="${toastId}" class="toast show ${bgClass} border-0 shadow-lg mb-2" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-dark text-white border-bottom border-secondary">
                    <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>
                    <strong class="me-auto">WEATHER ALERT DETECTED</strong>
                    <small class="text-white-50">Just now</small>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body fw-semibold">
                    <h6 class="fw-bold mb-1">${eventType} Detected</h6>
                    <p class="mb-0 small">${city} (${alertData.state || "India"}) - Severity: <strong>${severity}</strong></p>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML("beforeend", toastHtml);
        setTimeout(() => {
            const el = document.getElementById(toastId);
            if (el) el.remove();
        }, 8000);
    }

    // 3. Load & Render Alerts Data
    function loadAlertsData(page = 1) {
        currentPage = page;

        const eventType = document.getElementById("filter-event-type").value;
        const severity = document.getElementById("filter-severity").value;
        const status = document.getElementById("filter-status").value;
        const state = document.getElementById("filter-state").value;
        const city = document.getElementById("filter-city").value;

        const url = `/api/alerts?event_type=${encodeURIComponent(eventType)}&severity=${encodeURIComponent(severity)}&status=${encodeURIComponent(status)}&state=${encodeURIComponent(state)}&city=${encodeURIComponent(city)}&page=${page}&per_page=12`;

        fetch(url)
            .then(res => res.json())
            .then(response => {
                if (response.success && response.data) {
                    const data = response.data;
                    renderSummaryCards(data.summary);
                    renderAlertCards(data.alerts);
                    renderPagination(data.pagination);
                    renderMapMarkers(data.alerts);
                    renderTimeline(data.timeline);
                    renderCharts(data.analytics);
                }
            })
            .catch(err => console.error("Error fetching alerts:", err));
    }

    // Render 6 Summary Cards
    function renderSummaryCards(summary) {
        if (!summary) return;
        document.getElementById("card-active-alerts").innerText = summary.total_active || 0;
        document.getElementById("card-high-alerts").innerText = summary.high_severity || 0;
        document.getElementById("card-medium-alerts").innerText = summary.medium_severity || 0;
        document.getElementById("card-low-alerts").innerText = summary.low_severity || 0;
        document.getElementById("card-event-types").innerText = summary.active_event_types || 0;
        document.getElementById("card-resolved-alerts").innerText = summary.total_resolved || 0;
    }

    // Render Alert Cards Grid
    function renderAlertCards(alerts) {
        const container = document.getElementById("alert-cards-container");
        const emptyState = document.getElementById("alerts-empty-state");
        const countBadge = document.getElementById("alert-count-badge");

        if (!container) return;
        container.innerHTML = "";

        if (!alerts || alerts.length === 0) {
            emptyState.classList.remove("d-none");
            countBadge.innerText = "0 Alerts";
            return;
        }

        emptyState.classList.add("d-none");
        countBadge.innerText = `${alerts.length} Alerts`;

        alerts.forEach(alert => {
            let cardBorderClass = "alert-card-low";
            let severityBadgeClass = "bg-warning text-dark";

            if (alert.status === "Resolved") {
                cardBorderClass = "alert-card-resolved";
                severityBadgeClass = "bg-success text-white";
            } else if (alert.severity === "HIGH") {
                cardBorderClass = "alert-card-high";
                severityBadgeClass = "bg-danger text-white";
            } else if (alert.severity === "MEDIUM") {
                cardBorderClass = "alert-card-medium";
                severityBadgeClass = "bg-warning-subtle text-dark border border-warning";
            }

            const tempStr = alert.temperature !== null ? `${alert.temperature}°C` : "N/A";
            const confidenceStr = `${(alert.event_confidence || 0).toFixed(1)}%`;

            const cardHtml = `
                <div class="col-12 col-md-6">
                    <div class="card shadow-sm border-0 ${cardBorderClass} h-100">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="badge ${severityBadgeClass} px-2 py-1 mb-1">${alert.severity} SEVERITY</span>
                                    <h6 class="fw-bold text-dark mb-0">${alert.event_type}</h6>
                                </div>
                                <span class="badge ${alert.status === 'Active' ? 'bg-danger-subtle text-danger border border-danger' : 'bg-success-subtle text-success'} rounded-pill">
                                    ${alert.status}
                                </span>
                            </div>
                            <p class="text-muted small mb-2">
                                <i class="bi bi-geo-alt-fill text-danger me-1"></i><strong>${alert.city}</strong>${alert.state ? ', ' + alert.state : ''}
                            </p>
                            <div class="bg-light p-2 rounded mb-2 border">
                                <div class="row text-center g-1 small">
                                    <div class="col-4">
                                        <span class="text-muted d-block" style="font-size: 0.75rem;">Temp</span>
                                        <span class="fw-bold text-danger">${tempStr}</span>
                                    </div>
                                    <div class="col-4">
                                        <span class="text-muted d-block" style="font-size: 0.75rem;">Humidity</span>
                                        <span class="fw-bold text-primary">${alert.humidity !== null ? alert.humidity + '%' : 'N/A'}</span>
                                    </div>
                                    <div class="col-4">
                                        <span class="text-muted d-block" style="font-size: 0.75rem;">Confidence</span>
                                        <span class="fw-bold text-dark">${confidenceStr}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mt-2 pt-2 border-top">
                                <span class="text-muted small" style="font-size: 0.75rem;">
                                    <i class="bi bi-clock me-1"></i>${alert.detected_at}
                                </span>
                                <button class="btn btn-outline-dark btn-sm py-0 px-2 btn-inspect-alert" data-alert-id="${alert.id}">
                                    <i class="bi bi-eye me-1"></i> Inspect
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML("beforeend", cardHtml);
        });

        // Attach event listeners to Inspect buttons
        document.querySelectorAll(".btn-inspect-alert").forEach(btn => {
            btn.addEventListener("click", function () {
                const alertId = this.getAttribute("data-alert-id");
                openAlertDetailModal(alertId);
            });
        });
    }

    // Render Pagination Controls
    function renderPagination(pagination) {
        const pagContainer = document.getElementById("alerts-pagination");
        if (!pagContainer || !pagination) return;

        totalPages = pagination.total_pages || 1;
        if (totalPages <= 1) {
            pagContainer.classList.add("d-none");
            return;
        }

        pagContainer.classList.remove("d-none");
        document.getElementById("pagination-info").innerText = `Page ${pagination.current_page} of ${pagination.total_pages} (${pagination.total_count} alerts total)`;

        const btnPrev = document.getElementById("btn-prev-page");
        const btnNext = document.getElementById("btn-next-page");

        btnPrev.disabled = pagination.current_page <= 1;
        btnNext.disabled = pagination.current_page >= pagination.total_pages;
    }

    // Render Leaflet Map Markers
    function renderMapMarkers(alerts) {
        if (!alertMap || !mapMarkersGroup) return;

        mapMarkersGroup.clearLayers();

        if (!alerts || alerts.length === 0) return;

        const bounds = [];

        alerts.forEach(alert => {
            if (alert.latitude !== null && alert.longitude !== null) {
                const icon = getMarkerIcon(alert.severity, alert.status);
                const marker = L.marker([alert.latitude, alert.longitude], { icon: icon });

                const popupHtml = `
                    <div style="min-width: 180px;">
                        <span class="badge ${alert.severity === 'HIGH' ? 'bg-danger' : alert.severity === 'MEDIUM' ? 'bg-warning text-dark' : 'bg-info'} mb-1">${alert.severity}</span>
                        <h6 style="margin: 2px 0; font-weight: bold;">${alert.event_type}</h6>
                        <p style="margin: 0; font-size: 0.85rem; color: #555;"><strong>${alert.city}</strong>, ${alert.state}</p>
                        <hr style="margin: 5px 0;">
                        <p style="margin: 0; font-size: 0.8rem;">Temp: <strong>${alert.temperature !== null ? alert.temperature + '°C' : 'N/A'}</strong></p>
                        <p style="margin: 0; font-size: 0.8rem;">Detected: ${alert.detected_at}</p>
                    </div>
                `;

                marker.bindPopup(popupHtml);
                mapMarkersGroup.addLayer(marker);
                bounds.push([alert.latitude, alert.longitude]);
            }
        });

        if (bounds.length > 0) {
            alertMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
        }
    }

    // Render Timeline Sidebar Feed
    function renderTimeline(timeline) {
        const container = document.getElementById("timeline-container");
        if (!container) return;
        container.innerHTML = "";

        if (!timeline || timeline.length === 0) {
            container.innerHTML = `<div class="p-3 text-muted text-center small">No recent alert events</div>`;
            return;
        }

        timeline.forEach(t => {
            let iconClass = "bi-bell-fill text-warning";
            if (t.severity === "HIGH") iconClass = "bi-exclamation-triangle-fill text-danger";

            const itemHtml = `
                <a href="#" class="list-group-item list-group-item-action py-2 px-3 timeline-item" data-alert-id="${t.id}">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <span class="small fw-bold text-dark"><i class="bi ${iconClass} me-1"></i>${t.event_type}</span>
                        <small class="text-muted" style="font-size: 0.75rem;">${t.detected_at}</small>
                    </div>
                    <p class="mb-0 small text-muted">${t.city}${t.state ? ', ' + t.state : ''} - <span class="fw-semibold">${t.temperature !== null ? t.temperature + '°C' : ''}</span></p>
                </a>
            `;
            container.insertAdjacentHTML("beforeend", itemHtml);
        });

        document.querySelectorAll(".timeline-item").forEach(item => {
            item.addEventListener("click", function (e) {
                e.preventDefault();
                const alertId = this.getAttribute("data-alert-id");
                openAlertDetailModal(alertId);
            });
        });
    }

    // Render Chart.js Analytics Charts
    function renderCharts(analytics) {
        if (!analytics) return;

        // 1. Severity Chart (Doughnut)
        const ctxSev = document.getElementById("chart-severity");
        if (ctxSev) {
            const labels = (analytics.severity_distribution || []).map(item => item.severity);
            const data = (analytics.severity_distribution || []).map(item => parseInt(item.count));

            if (chartSeverity) chartSeverity.destroy();
            chartSeverity = new Chart(ctxSev, {
                type: "doughnut",
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: ["#dc3545", "#fd7e14", "#ffc107", "#198754"]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: "bottom" } }
                }
            });
        }

        // 2. Event Types Chart (Bar)
        const ctxEvt = document.getElementById("chart-events");
        if (ctxEvt) {
            const labels = (analytics.event_distribution || []).map(item => item.event_type);
            const data = (analytics.event_distribution || []).map(item => parseInt(item.count));

            if (chartEvents) chartEvents.destroy();
            chartEvents = new Chart(ctxEvt, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Alert Count",
                        data: data,
                        backgroundColor: "#0d6efd"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                }
            });
        }

        // 3. State Distribution Chart (Horizontal Bar)
        const ctxState = document.getElementById("chart-states");
        if (ctxState) {
            const labels = (analytics.state_distribution || []).map(item => item.state);
            const data = (analytics.state_distribution || []).map(item => parseInt(item.count));

            if (chartStates) chartStates.destroy();
            chartStates = new Chart(ctxState, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Alert Count",
                        data: data,
                        backgroundColor: "#6c757d"
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { x: { beginAtZero: true, ticks: { precision: 0 } } }
                }
            });
        }
    }

    // 4. Open Alert Inspection Modal
    function openAlertDetailModal(alertId) {
        currentModalAlertId = alertId;

        const loadingDiv = document.getElementById("modal-alert-loading");
        const contentDiv = document.getElementById("modal-alert-content");
        const modal = new bootstrap.Modal(document.getElementById("alertDetailModal"));

        loadingDiv.classList.remove("d-none");
        contentDiv.classList.add("d-none");
        modal.show();

        fetch(`/api/alerts/${alertId}`)
            .then(res => res.json())
            .then(response => {
                if (response.success && response.data) {
                    const alert = response.data.alert;
                    const reports = response.data.related_reports;

                    document.getElementById("modal-event-title").innerText = alert.title || alert.event_type;
                    document.getElementById("modal-location").innerHTML = `<i class="bi bi-geo-alt-fill text-danger me-1"></i>${alert.city}${alert.state ? ', ' + alert.state : ''}`;
                    document.getElementById("modal-detected-at").innerText = `Detected: ${alert.detected_at}`;

                    const sevBadge = document.getElementById("modal-severity-badge");
                    sevBadge.innerText = `${alert.severity} SEVERITY`;
                    if (alert.severity === "HIGH") sevBadge.className = "badge bg-danger fs-6 me-2";
                    else if (alert.severity === "MEDIUM") sevBadge.className = "badge bg-warning text-dark fs-6 me-2";
                    else sevBadge.className = "badge bg-info text-dark fs-6 me-2";

                    const statusBadge = document.getElementById("modal-status-badge");
                    statusBadge.innerText = alert.status;
                    statusBadge.className = alert.status === "Active" ? "badge bg-danger fs-6 me-2" : "badge bg-success fs-6 me-2";

                    const sourceBadge = document.getElementById("modal-source-badge");
                    if (sourceBadge) {
                        sourceBadge.innerText = alert.source || "Automated System";
                        sourceBadge.className = alert.source === "SACHET / NDMA" ? "badge bg-primary fs-6" : "badge bg-secondary fs-6";
                    }

                    const confidence = (alert.event_confidence || 0).toFixed(1);
                    document.getElementById("modal-confidence-bar").style.width = `${confidence}%`;
                    document.getElementById("modal-confidence-text").innerText = `${confidence}%`;

                    document.getElementById("modal-temp").innerText = alert.temperature !== null ? `${alert.temperature}°C` : "N/A";
                    document.getElementById("modal-humidity").innerText = alert.humidity !== null ? `${alert.humidity}%` : "N/A";
                    document.getElementById("modal-wind").innerText = alert.wind_speed !== null ? `${alert.wind_speed} km/h` : "N/A";
                    document.getElementById("modal-condition").innerText = alert.weather_condition || alert.weather_description || "N/A";

                    // Description & Advisory rendering
                    const descBox = document.getElementById("modal-description-box");
                    const descText = document.getElementById("modal-description-text");
                    const instText = document.getElementById("modal-instruction-text");
                    const instContainer = document.getElementById("modal-instruction-container");
                    const linkContainer = document.getElementById("modal-link-container");
                    const linkUrl = document.getElementById("modal-link-url");

                    if (descBox && descText) {
                        if (alert.description || alert.instruction || alert.link) {
                            descBox.classList.remove("d-none");
                            descText.innerText = alert.description || alert.title || "Official weather alert bulletin issued.";

                            if (instContainer && instText) {
                                if (alert.instruction) {
                                    instContainer.classList.remove("d-none");
                                    instText.innerText = alert.instruction;
                                } else {
                                    instContainer.classList.add("d-none");
                                }
                            }
                            if (linkContainer && linkUrl) {
                                if (alert.link) {
                                    linkContainer.classList.remove("d-none");
                                    linkUrl.href = alert.link;
                                } else {
                                    linkContainer.classList.add("d-none");
                                }
                            }
                        } else {
                            descBox.classList.add("d-none");
                        }
                    }

                    // Render matching reports table
                    const reportsBody = document.getElementById("modal-reports-body");
                    reportsBody.innerHTML = "";
                    if (!reports || reports.length === 0) {
                        reportsBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted small">No citizen reports recorded for this city yet.</td></tr>`;
                    } else {
                        reports.forEach(r => {
                            const tr = `
                                <tr>
                                    <td><span class="badge bg-secondary-subtle text-dark">${r.source}</span></td>
                                    <td class="small text-truncate" style="max-width: 200px;">${r.report_text}</td>
                                    <td><span class="badge bg-light text-dark border">${r.verification_result}</span></td>
                                    <td class="fw-bold small">${r.trust_score !== null ? r.trust_score + '%' : 'N/A'}</td>
                                    <td class="small text-muted">${r.report_datetime}</td>
                                </tr>
                            `;
                            reportsBody.insertAdjacentHTML("beforeend", tr);
                        });
                    }

                    // Handle Resolve button visibility
                    const btnResolve = document.getElementById("modal-btn-resolve");
                    if (btnResolve) {
                        if (alert.status === "Active" && (window.CURRENT_USER_ROLE === "admin" || window.CURRENT_USER_ROLE === "analyst")) {
                            btnResolve.classList.remove("d-none");
                        } else {
                            btnResolve.classList.add("d-none");
                        }
                    }

                    loadingDiv.classList.add("d-none");
                    contentDiv.classList.remove("d-none");
                }
            })
            .catch(err => {
                console.error("Error loading alert modal details:", err);
                loadingDiv.innerHTML = `<div class="alert alert-danger small">Failed to load alert details.</div>`;
            });
    }

    // 5. Handle Admin Resolve Alert Action
    const btnResolveModal = document.getElementById("modal-btn-resolve");
    if (btnResolveModal) {
        btnResolveModal.addEventListener("click", function () {
            if (!currentModalAlertId) return;

            if (!confirm(`Are you sure you want to mark Weather Alert #${currentModalAlertId} as Resolved?`)) {
                return;
            }

            fetch(`/api/alerts/${currentModalAlertId}/resolve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            })
                .then(res => res.json())
                .then(response => {
                    if (response.success) {
                        alert(response.message || "Alert resolved successfully.");
                        const modalEl = document.getElementById("alertDetailModal");
                        const modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) modalInstance.hide();
                        loadAlertsData(currentPage);
                    } else {
                        alert("Error resolving alert: " + (response.error || "Action failed"));
                    }
                })
                .catch(err => alert("Server error resolving alert: " + err));
        });
    }

    // 6. Setup Form & Button Listeners
    const filterForm = document.getElementById("filter-alerts-form");
    if (filterForm) {
        filterForm.addEventListener("submit", function (e) {
            e.preventDefault();
            loadAlertsData(1);
        });
    }

    const btnReset = document.getElementById("btn-reset-filters");
    if (btnReset) {
        btnReset.addEventListener("click", function () {
            document.getElementById("filter-event-type").value = "all";
            document.getElementById("filter-severity").value = "all";
            document.getElementById("filter-status").value = "Active";
            document.getElementById("filter-state").value = "all";
            document.getElementById("filter-city").value = "";
            loadAlertsData(1);
        });
    }

    const btnRefresh = document.getElementById("btn-refresh-alerts");
    if (btnRefresh) {
        btnRefresh.addEventListener("click", function () {
            loadAlertsData(currentPage);
        });
    }

    document.getElementById("btn-prev-page")?.addEventListener("click", () => {
        if (currentPage > 1) loadAlertsData(currentPage - 1);
    });

    document.getElementById("btn-next-page")?.addEventListener("click", () => {
        if (currentPage < totalPages) loadAlertsData(currentPage + 1);
    });

    // 7. Initial Initialization
    initAlertMap();
    initSocketIO();
    loadAlertsData(1);
});
