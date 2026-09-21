/**
 * Data Export & Weather Intelligence Reports Controller
 * Handles real-time preview updating, filter parameter binding, CSV/JSON downloads,
 * Intelligence Summary rendering, and SocketIO live updates.
 */

document.addEventListener("DOMContentLoaded", function () {

    // 1. Build Query Parameters from Filter Form
    function getFilterQueryParams() {
        const startDate = document.getElementById("filter-start-date").value;
        const endDate = document.getElementById("filter-end-date").value;
        const eventType = document.getElementById("filter-event-type").value;
        const state = document.getElementById("filter-state").value;
        const city = document.getElementById("filter-city").value;
        const source = document.getElementById("filter-source").value;
        const verStatus = document.getElementById("filter-verification-status").value;
        const trustLevel = document.getElementById("filter-trust-level").value;

        const params = new URLSearchParams();
        if (startDate) params.append("start_date", startDate);
        if (endDate) params.append("end_date", endDate);
        if (eventType) params.append("event_type", eventType);
        if (state) params.append("state", state);
        if (city) params.append("city", city);
        if (source) params.append("source", source);
        if (verStatus) params.append("verification_status", verStatus);
        if (trustLevel) params.append("trust_level", trustLevel);

        return params.toString();
    }

    // 2. Fetch & Render Live Export Summary Preview
    function loadSummaryPreview() {
        const queryStr = getFilterQueryParams();
        fetch(`/api/export/summary?${queryStr}`)
            .then(res => res.json())
            .then(response => {
                if (response.success && response.data) {
                    const data = response.data;
                    document.getElementById("preview-total-reports").innerText = data.total_reports || 0;
                    document.getElementById("preview-date-range").innerText = data.date_range || "N/A";
                    document.getElementById("preview-events-count").innerText = data.events_count || 0;
                    document.getElementById("preview-states-count").innerText = data.states_count || 0;
                    document.getElementById("preview-avg-trust").innerText = `${(data.average_trust || 0).toFixed(1)}%`;
                }
            })
            .catch(err => console.error("Error fetching export summary preview:", err));
    }

    // 3. Fetch & Render Weather Intelligence Executive Summary
    function loadIntelligenceSummary() {
        const previewContainer = document.getElementById("intelligence-summary-preview");
        if (!previewContainer) return;

        previewContainer.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading Intelligence Report...</span>
                </div>
            </div>
        `;

        fetch("/api/intelligence-summary")
            .then(res => res.json())
            .then(response => {
                if (response.success && response.data) {
                    const d = response.data;
                    const ov = d.national_overview;
                    const me = d.major_events;
                    const vo = d.verification_overview;
                    const dq = d.data_quality;
                    const al = d.alert_status;

                    let eventsListHtml = "";
                    (me.most_common_events || []).forEach(ev => {
                        eventsListHtml += `<li><strong>${ev.event_type}:</strong> ${ev.count} occurrences</li>`;
                    });

                    let highConfHtml = "";
                    (me.highest_confidence_events || []).forEach(ev => {
                        highConfHtml += `<li><strong>${ev.city} (${ev.state}):</strong> ${ev.event_type} (${ev.max_conf}% AI Confidence)</li>`;
                    });

                    let obsHtml = "";
                    (d.key_observations || []).forEach(obs => {
                        obsHtml += `<li class="mb-1"><i class="bi bi-check2-circle text-primary me-2"></i>${obs}</li>`;
                    });

                    const reportHtml = `
                        <div class="d-flex justify-content-between align-items-center border-bottom pb-3 mb-3">
                            <div>
                                <h5 class="fw-bold text-dark mb-0">NATIONAL WEATHER INTELLIGENCE EXECUTIVE REPORT</h5>
                                <small class="text-muted">Generated At: ${d.generated_at}</small>
                            </div>
                            <span class="badge bg-success-subtle text-success border border-success px-3 py-2">Validated Empirical Dataset</span>
                        </div>

                        <div class="row g-4 mb-4">
                            <!-- Section 1: National Overview -->
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded border h-100">
                                    <h6 class="fw-bold text-primary border-bottom pb-2 mb-2"><i class="bi bi-globe me-2"></i>NATIONAL OVERVIEW</h6>
                                    <ul class="list-unstyled mb-0 small">
                                        <li class="mb-1"><strong>Total Weather Reports:</strong> ${ov.total_reports}</li>
                                        <li class="mb-1"><strong>API Weather Observations:</strong> ${ov.total_observations}</li>
                                        <li class="mb-1"><strong>Active Weather Alerts:</strong> ${ov.active_alerts}</li>
                                        <li class="mb-1"><strong>States Represented:</strong> ${ov.states_represented}</li>
                                        <li class="mb-1"><strong>Cities Represented:</strong> ${ov.cities_represented}</li>
                                        <li class="mb-0"><strong>Average Source Trust:</strong> ${ov.average_trust_score}%</li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Section 2: Verification Status & Quality -->
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded border h-100">
                                    <h6 class="fw-bold text-success border-bottom pb-2 mb-2"><i class="bi bi-shield-check me-2"></i>VERIFICATION & DATA QUALITY</h6>
                                    <ul class="list-unstyled mb-0 small">
                                        <li class="mb-1"><strong>Verified (Likely Consistent):</strong> ${vo.verified_reports}</li>
                                        <li class="mb-1"><strong>Needs Verification:</strong> ${vo.needs_verification}</li>
                                        <li class="mb-1"><strong>Suspicious Reports:</strong> ${vo.suspicious}</li>
                                        <li class="mb-1"><strong>Unverified Reports:</strong> ${vo.unverified}</li>
                                        <li class="mb-1"><strong>Unique Reports:</strong> ${dq.unique_reports}</li>
                                        <li class="mb-0"><strong>Potential Duplicates:</strong> ${dq.potential_duplicates}</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Section 3: Event Intelligence -->
                        <div class="row g-4 mb-4">
                            <div class="col-md-6">
                                <div class="p-3 bg-white border rounded shadow-sm h-100">
                                    <h6 class="fw-bold text-dark border-bottom pb-2 mb-2"><i class="bi bi-cloud-lightning me-2"></i>MOST FREQUENT WEATHER EVENTS</h6>
                                    <ul class="small mb-0 ps-3">
                                        ${eventsListHtml || '<li>No events recorded</li>'}
                                    </ul>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="p-3 bg-white border rounded shadow-sm h-100">
                                    <h6 class="fw-bold text-dark border-bottom pb-2 mb-2"><i class="bi bi-cpu me-2"></i>HIGHEST CONFIDENCE DETECTIONS</h6>
                                    <ul class="small mb-0 ps-3">
                                        ${highConfHtml || '<li>No high confidence events recorded</li>'}
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Section 4: Alert Status -->
                        <div class="p-3 bg-danger-subtle rounded border border-danger mb-4">
                            <h6 class="fw-bold text-danger mb-2"><i class="bi bi-bell-fill me-2"></i>NATIONAL ALERT STATUS SUMMARY</h6>
                            <div class="row text-center g-2 small">
                                <div class="col"><strong>Active:</strong> ${al.active_alerts}</div>
                                <div class="col text-danger"><strong>High Severity:</strong> ${al.high_severity}</div>
                                <div class="col text-warning"><strong>Medium Severity:</strong> ${al.medium_severity}</div>
                                <div class="col text-info"><strong>Low Severity:</strong> ${al.low_severity}</div>
                                <div class="col text-success"><strong>Resolved:</strong> ${al.resolved_alerts}</div>
                            </div>
                        </div>

                        <!-- Section 5: Key Observations -->
                        <div class="p-3 bg-light rounded border">
                            <h6 class="fw-bold text-dark border-bottom pb-2 mb-2"><i class="bi bi-journal-text me-2"></i>KEY METEOROLOGICAL OBSERVATIONS</h6>
                            <ul class="list-unstyled mb-0 small">
                                ${obsHtml}
                            </ul>
                        </div>
                    `;

                    previewContainer.innerHTML = reportHtml;
                }
            })
            .catch(err => {
                console.error("Error loading intelligence summary:", err);
                previewContainer.innerHTML = `<div class="alert alert-danger small mb-0">Failed to load intelligence summary.</div>`;
            });
    }

    // 4. SocketIO Connection for Live Count Updates
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

        socket.on("weather_update", function () {
            loadSummaryPreview();
        });

        socket.on("new_report", function () {
            loadSummaryPreview();
        });

        socket.on("weather_alert", function () {
            loadSummaryPreview();
        });
    }

    // 5. Setup Action Button Event Listeners
    document.getElementById("export-filter-form")?.addEventListener("submit", function (e) {
        e.preventDefault();
        loadSummaryPreview();
    });

    document.getElementById("btn-clear-filters")?.addEventListener("click", function () {
        document.getElementById("filter-start-date").value = "";
        document.getElementById("filter-end-date").value = "";
        document.getElementById("filter-event-type").value = "all";
        document.getElementById("filter-state").value = "all";
        document.getElementById("filter-city").value = "";
        document.getElementById("filter-source").value = "all";
        document.getElementById("filter-verification-status").value = "all";
        document.getElementById("filter-trust-level").value = "all";
        loadSummaryPreview();
    });

    document.getElementById("btn-export-reports-csv")?.addEventListener("click", function () {
        window.location.href = `/api/export/reports/csv?${getFilterQueryParams()}`;
    });

    document.getElementById("btn-export-reports-json")?.addEventListener("click", function () {
        window.location.href = `/api/export/reports/json?${getFilterQueryParams()}`;
    });

    document.getElementById("btn-export-weather-csv")?.addEventListener("click", function () {
        window.location.href = `/api/export/weather/csv?${getFilterQueryParams()}`;
    });

    document.getElementById("btn-export-alerts-csv")?.addEventListener("click", function () {
        window.location.href = `/api/export/alerts/csv?${getFilterQueryParams()}`;
    });

    document.getElementById("btn-export-audit-csv")?.addEventListener("click", function () {
        window.location.href = `/api/export/admin-audit/csv`;
    });

    document.getElementById("btn-generate-summary")?.addEventListener("click", function () {
        loadIntelligenceSummary();
    });

    document.getElementById("btn-download-summary")?.addEventListener("click", function () {
        window.location.href = `/api/export/intelligence-summary/download`;
    });

    // 6. Initial Load
    loadSummaryPreview();
    loadIntelligenceSummary();
    initSocketIO();
});
