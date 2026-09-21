/**
 * admin_dashboard.js
 * National Weather Intelligence Platform - Admin & Weather Report Verification Control Center
 */

document.addEventListener("DOMContentLoaded", function () {
    let currentPage = 1;
    const perPage = 20;

    // DOM Elements
    const summaryTotal = document.getElementById('admin-total-reports');
    const summaryUnverified = document.getElementById('admin-unverified-reports');
    const summaryNeeds = document.getElementById('admin-needs-verification');
    const summarySuspicious = document.getElementById('admin-suspicious-reports');
    const summaryVerified = document.getElementById('admin-verified-reports');
    const summaryDuplicates = document.getElementById('admin-duplicates');
    const summaryAvgTrust = document.getElementById('admin-avg-trust');

    const searchKeyword = document.getElementById('admin-search-keyword');
    const eventTypeSelect = document.getElementById('admin-event-type');
    const verificationSelect = document.getElementById('admin-verification-status');
    const duplicateSelect = document.getElementById('admin-duplicate-status');
    const applyBtn = document.getElementById('admin-apply-filters');
    const resetBtn = document.getElementById('admin-clear-filters');

    const showingCount = document.getElementById('admin-showing-count');
    const totalCount = document.getElementById('admin-total-count');
    const tableBody = document.getElementById('admin-reports-table-body');
    const emptyState = document.getElementById('admin-empty-state');
    const paginationContainer = document.getElementById('admin-pagination-container');

    const errorAlert = document.getElementById('admin-error-alert');
    const errorText = document.getElementById('admin-error-text');

    // Modal Instance
    const modalEl = document.getElementById('adminReviewModal');
    let reviewModal = null;
    if (modalEl && typeof bootstrap !== 'undefined') {
        reviewModal = new bootstrap.Modal(modalEl);
    }

    // Helper: Escape HTML
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatDT(str) {
        if (!str) return 'N/A';
        try {
            const d = new Date(str);
            if (isNaN(d.getTime())) return str;
            return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
        } catch (e) {
            return str;
        }
    }

    function showError(msg) {
        if (errorAlert && errorText) {
            errorText.textContent = msg;
            errorAlert.classList.remove('d-none');
        }
    }

    function hideError() {
        if (errorAlert) errorAlert.classList.add('d-none');
    }

    // Fetch Summary Metrics
    async function loadSummary() {
        try {
            const res = await fetch('/api/admin/summary');
            const json = await res.json();
            if (json.status === 'success' && json.summary) {
                const s = json.summary;
                if (summaryTotal) summaryTotal.textContent = s.total_reports || 0;
                if (summaryUnverified) summaryUnverified.textContent = s.unverified_reports || 0;
                if (summaryNeeds) summaryNeeds.textContent = s.needs_verification || 0;
                if (summarySuspicious) summarySuspicious.textContent = s.suspicious_reports || 0;
                if (summaryVerified) summaryVerified.textContent = s.verified_reports || 0;
                if (summaryDuplicates) summaryDuplicates.textContent = s.potential_duplicates || 0;
                if (summaryAvgTrust) summaryAvgTrust.textContent = `${Number(s.average_trust_score || 0).toFixed(1)} / 100`;
            }
        } catch (e) {
            console.error("Failed to load admin summary:", e);
        }
    }

    // Fetch Admin Reports List
    async function loadReports(page = 1) {
        currentPage = page;
        hideError();

        const params = new URLSearchParams({
            page: currentPage,
            per_page: perPage
        });

        if (searchKeyword && searchKeyword.value.trim()) params.append('keyword', searchKeyword.value.trim());
        if (eventTypeSelect && eventTypeSelect.value !== 'All') params.append('event_type', eventTypeSelect.value);
        if (verificationSelect && verificationSelect.value !== 'All') params.append('verification', verificationSelect.value);
        if (duplicateSelect && duplicateSelect.value !== 'All') params.append('duplicate_status', duplicateSelect.value);

        try {
            const res = await fetch(`/api/admin/reports?${params.toString()}`);
            const json = await res.json();

            if (json.status === 'success' && json.data) {
                renderTable(json.data.reports || []);
                renderPagination(json.data.page, json.data.total_pages, json.data.total);
                if (showingCount) showingCount.textContent = json.data.reports ? json.data.reports.length : 0;
                if (totalCount) totalCount.textContent = json.data.total || 0;
            } else {
                showError(json.message || "Failed to load admin reports.");
                renderTable([]);
            }
        } catch (e) {
            console.error("Error fetching admin reports:", e);
            showError("Network error while retrieving admin reports.");
            renderTable([]);
        }
    }

    // Render Admin Table Rows
    function renderTable(reports) {
        if (!tableBody) return;
        tableBody.innerHTML = '';

        if (!reports || reports.length === 0) {
            if (emptyState) emptyState.classList.remove('d-none');
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');

        reports.forEach(report => {
            const tr = document.createElement('tr');

            // Attention Level Badge
            const att = report.attention_level || 'MEDIUM';
            let attBadge = '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-triangle me-1"></i>MEDIUM</span>';
            if (att === 'HIGH') {
                attBadge = '<span class="badge bg-danger"><i class="bi bi-exclamation-octagon-fill me-1"></i>HIGH</span>';
            } else if (att === 'LOW') {
                attBadge = '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>LOW</span>';
            }

            // Source & Verification badges
            const src = report.source || 'Citizen Report';
            const vRes = report.verification_result || report.verification_status || 'Unverified';
            let vBadge = '<span class="badge bg-secondary px-2 py-1">Unverified</span>';
            if (vRes === 'Likely Consistent' || vRes === 'Verified') {
                vBadge = '<span class="badge bg-success px-2 py-1"><i class="bi bi-check-circle-fill me-1"></i>Verified</span>';
            } else if (vRes === 'Needs Verification') {
                vBadge = '<span class="badge bg-warning text-dark px-2 py-1"><i class="bi bi-question-circle-fill me-1"></i>Needs Verification</span>';
            } else if (vRes === 'Suspicious') {
                vBadge = '<span class="badge bg-danger px-2 py-1"><i class="bi bi-shield-x me-1"></i>Suspicious</span>';
            }

            // Trust Score badge
            const tVal = report.trust_score !== null && report.trust_score !== undefined ? Number(report.trust_score) : 50.0;
            let tBadge = tVal >= 80.0 ? 'bg-success' : (tVal >= 50.0 ? 'bg-warning text-dark' : 'bg-danger');

            // Duplicate status
            const dupStat = report.duplicate_status || (report.is_duplicate ? 'Potential Duplicate' : 'Unique');
            let dupBadge = '<span class="badge bg-info-subtle text-info-emphasis px-2 py-1">Unique</span>';
            if (dupStat === 'Potential Duplicate') {
                dupBadge = '<span class="badge bg-danger px-2 py-1"><i class="bi bi-files me-1"></i>Duplicate</span>';
            } else if (dupStat === 'Related Report') {
                dupBadge = '<span class="badge bg-warning-subtle text-dark px-2 py-1"><i class="bi bi-diagram-3 me-1"></i>Related</span>';
            }

            const aiConf = report.ai_confidence !== null ? Number(report.ai_confidence).toFixed(1) : 'N/A';
            const locationStr = `${escapeHtml(report.city || 'N/A')}${report.state ? ', <small class="text-muted">' + escapeHtml(report.state) + '</small>' : ''}`;

            tr.innerHTML = `
                <td>${attBadge}</td>
                <td><span class="fw-bold">#${report.id}</span></td>
                <td><span class="badge bg-secondary-subtle text-dark">${escapeHtml(src)}</span></td>
                <td><span class="badge bg-info-subtle text-info-emphasis">${escapeHtml(report.event_type || 'General')}</span></td>
                <td>${locationStr}</td>
                <td><small class="text-muted">${formatDT(report.report_datetime || report.created_at)}</small></td>
                <td>${vBadge}</td>
                <td>
                    <span class="badge ${tBadge} px-2 py-1 d-inline-block">${tVal.toFixed(1)}%</span>
                </td>
                <td>${dupBadge}</td>
                <td><span class="fw-semibold text-secondary">${aiConf}%</span></td>
                <td class="text-end pe-3 text-nowrap">
                    <button type="button" class="btn btn-primary btn-sm btn-admin-review fw-bold me-1" data-id="${report.id}">
                        <i class="bi bi-shield-check me-1"></i> Review & Verify
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm btn-quick-suspicious" data-id="${report.id}" title="Mark Suspicious">
                        <i class="bi bi-shield-x"></i>
                    </button>
                </td>
            `;

            tableBody.appendChild(tr);
        });

        // Attach action click listeners
        document.querySelectorAll('.btn-admin-review').forEach(btn => {
            btn.addEventListener('click', function () {
                const rId = this.getAttribute('data-id');
                openReviewModal(rId);
            });
        });

        document.querySelectorAll('.btn-quick-suspicious').forEach(btn => {
            btn.addEventListener('click', function () {
                const rId = this.getAttribute('data-id');
                quickMarkSuspicious(rId);
            });
        });
    }

    // Render Pagination
    function renderPagination(page, totalPages, total) {
        if (!paginationContainer) return;
        paginationContainer.innerHTML = '';

        if (totalPages <= 1) return;

        const nav = document.createElement('nav');
        const ul = document.createElement('ul');
        ul.className = 'pagination pagination-sm mb-0';

        // Prev Button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${page <= 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#">&laquo; Prev</a>`;
        if (page > 1) {
            prevLi.addEventListener('click', (e) => {
                e.preventDefault();
                loadReports(page - 1);
            });
        }
        ul.appendChild(prevLi);

        for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === page ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            if (i !== page) {
                const targetPage = i;
                li.addEventListener('click', (e) => {
                    e.preventDefault();
                    loadReports(targetPage);
                });
            }
            ul.appendChild(li);
        }

        // Next Button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${page >= totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#">Next &raquo;</a>`;
        if (page < totalPages) {
            nextLi.addEventListener('click', (e) => {
                e.preventDefault();
                loadReports(page + 1);
            });
        }
        ul.appendChild(nextLi);

        nav.appendChild(ul);
        paginationContainer.appendChild(nav);
    }

    // Open Admin Review Modal & Populate Evidence
    async function openReviewModal(reportId) {
        try {
            const res = await fetch(`/api/admin/report/${reportId}`);
            const json = await res.json();

            if (json.status === 'success' && json.data) {
                const d = json.data;
                const r = d.report;

                document.getElementById('modal-target-report-id').value = r.id;
                document.getElementById('modal-report-id').textContent = `#${r.id}`;

                // Attention badge
                const attEl = document.getElementById('modal-attention-badge');
                if (attEl) {
                    const att = d.attention_level || 'MEDIUM';
                    attEl.innerHTML = att === 'HIGH' ? '<span class="badge bg-danger fs-7">ATTENTION: HIGH</span>' :
                                      (att === 'LOW' ? '<span class="badge bg-success fs-7">ATTENTION: LOW</span>' :
                                      '<span class="badge bg-warning text-dark fs-7">ATTENTION: MEDIUM</span>');
                }

                document.getElementById('modal-source').textContent = r.source || 'Citizen Report';
                document.getElementById('modal-event-type').textContent = r.event_type || 'General';
                document.getElementById('modal-location').textContent = `${r.city || 'N/A'}${r.state ? ', ' + r.state : ''}`;
                document.getElementById('modal-datetime').textContent = formatDT(r.report_datetime || r.created_at);
                document.getElementById('modal-report-text').textContent = r.report_text || 'No text provided.';

                // Render Latest Weather Evidence Box
                const obsBox = document.getElementById('modal-obs-container');
                if (obsBox) {
                    if (d.latest_obs) {
                        const o = d.latest_obs;
                        obsBox.innerHTML = `
                            <div class="row g-2 fs-7">
                                <div class="col-6"><strong>Weather Condition:</strong> ${escapeHtml(o.weather_condition || 'N/A')}</div>
                                <div class="col-6"><strong>Temperature:</strong> ${o.temperature !== null ? o.temperature + ' °C' : 'N/A'}</div>
                                <div class="col-6"><strong>Humidity:</strong> ${o.humidity !== null ? o.humidity + ' %' : 'N/A'}</div>
                                <div class="col-6"><strong>Wind Speed:</strong> ${o.wind_speed !== null ? o.wind_speed + ' m/s' : 'N/A'}</div>
                                <div class="col-12"><strong>Description:</strong> ${escapeHtml(o.weather_description || 'N/A')}</div>
                                <div class="col-12 text-muted border-top pt-1 mt-1"><small>Recorded: ${formatDT(o.recorded_at || o.created_at)}</small></div>
                            </div>
                        `;
                    } else {
                        obsBox.innerHTML = '<span class="text-muted small">No recent official OpenWeather API observation found for this city.</span>';
                    }
                }

                // Render Duplicate Review Box
                const dupBox = document.getElementById('modal-duplicate-container');
                if (dupBox) {
                    const dupStat = r.duplicate_status || (r.is_duplicate ? 'Potential Duplicate' : 'Unique');
                    const dupSim = r.duplicate_similarity_score !== null ? Number(r.duplicate_similarity_score).toFixed(1) + '%' : 'N/A';
                    
                    let relatedHtml = '';
                    if (d.related_reports && d.related_reports.length > 0) {
                        relatedHtml = '<ul class="mb-0 ps-3 mt-1 fs-7">';
                        d.related_reports.forEach(rel => {
                            relatedHtml += `<li><strong>#${rel.id}</strong> - ${escapeHtml(rel.event_type)} (${escapeHtml(rel.city)}) - ${rel.duplicate_status || 'Related'}</li>`;
                        });
                        relatedHtml += '</ul>';
                    } else {
                        relatedHtml = '<span class="text-muted small d-block mt-1">No other reports in duplicate group.</span>';
                    }

                    dupBox.innerHTML = `
                        <div class="fs-7">
                            <div class="mb-1"><strong>Status:</strong> <span class="badge bg-secondary">${escapeHtml(dupStat)}</span> (Similarity: <strong>${dupSim}</strong>)</div>
                            <div class="mb-1"><strong>Duplicate Reason:</strong> ${escapeHtml(r.duplicate_reason || 'N/A')}</div>
                            <div class="mt-2 border-top pt-1"><strong>Related Group Reports:</strong> ${relatedHtml}</div>
                        </div>
                    `;
                }

                // Select current verification outcome radio button
                const currentRes = r.verification_result || r.verification_status || 'Needs Verification';
                const radioMap = {
                    'Verified': 'btn-v-verified',
                    'Likely Consistent': 'btn-v-likely',
                    'Needs Verification': 'btn-v-needs',
                    'Suspicious': 'btn-v-suspicious',
                    'Unverified': 'btn-v-unverified'
                };
                const targetRadioId = radioMap[currentRes] || 'btn-v-needs';
                const targetRadio = document.getElementById(targetRadioId);
                if (targetRadio) targetRadio.checked = true;

                // Verification Reason text field
                document.getElementById('modal-verify-reason').value = r.verification_reason || r.trust_reason || '';

                // Action History Log
                const histBox = document.getElementById('modal-history-container');
                if (histBox) {
                    if (d.action_history && d.action_history.length > 0) {
                        let hHtml = '<div class="list-group list-group-flush">';
                        d.action_history.forEach(act => {
                            hHtml += `
                                <div class="list-group-item bg-transparent px-0 py-1">
                                    <div class="d-flex justify-content-between">
                                        <strong>${escapeHtml(act.action_type)}</strong>
                                        <small class="text-muted">${formatDT(act.action_datetime)}</small>
                                    </div>
                                    <div class="small">By: ${escapeHtml(act.performed_by || 'Admin')} | Outcome: <span class="badge bg-secondary">${escapeHtml(act.new_verification)}</span></div>
                                    <div class="text-muted text-truncate" style="font-size: 0.75rem;">${escapeHtml(act.reason || 'No note')}</div>
                                </div>
                            `;
                        });
                        hHtml += '</div>';
                        histBox.innerHTML = hHtml;
                    } else {
                        histBox.innerHTML = '<span class="text-muted small">No manual admin actions logged for this report yet.</span>';
                    }
                }

                if (reviewModal) reviewModal.show();
            } else {
                alert(json.message || "Failed to load report for review.");
            }
        } catch (e) {
            console.error("Error opening review modal:", e);
            alert("Error fetching report verification details.");
        }
    }

    // Submit Verification Decision Form
    const verifyForm = document.getElementById('admin-verify-form');
    if (verifyForm) {
        verifyForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            const rId = document.getElementById('modal-target-report-id').value;
            const selectedRadio = document.querySelector('input[name="verify_result_choice"]:checked');
            if (!selectedRadio) {
                alert("Please select a verification outcome result.");
                return;
            }

            const newVerification = selectedRadio.value;
            const reason = document.getElementById('modal-verify-reason').value;

            try {
                const res = await fetch(`/api/admin/report/${rId}/verify`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        new_verification: newVerification,
                        reason: reason,
                        action_type: newVerification === 'Suspicious' ? 'Marked Suspicious' : (newVerification === 'Verified' ? 'Verified' : 'Updated Verification')
                    })
                });

                const json = await res.json();
                if (json.status === 'success') {
                    if (reviewModal) reviewModal.hide();
                    loadSummary();
                    loadReports(currentPage);
                } else {
                    alert(json.message || "Failed to update verification status.");
                }
            } catch (err) {
                console.error("Verification submit error:", err);
                alert("Error submitting verification decision.");
            }
        });
    }

    // Quick Mark Suspicious Action
    async function quickMarkSuspicious(reportId) {
        if (!confirm(`Are you sure you want to mark Report #${reportId} as Suspicious?`)) return;

        try {
            const res = await fetch(`/api/admin/report/${reportId}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    new_verification: 'Suspicious',
                    reason: 'Quick action: Marked suspicious by administrator after ground evidence review.',
                    action_type: 'Marked Suspicious'
                })
            });
            const json = await res.json();
            if (json.status === 'success') {
                loadSummary();
                loadReports(currentPage);
            } else {
                alert(json.message || "Failed to mark suspicious.");
            }
        } catch (e) {
            console.error("Quick mark suspicious error:", e);
        }
    }

    // Event Listeners for Filters
    if (applyBtn) {
        applyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            loadReports(1);
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (searchKeyword) searchKeyword.value = '';
            if (eventTypeSelect) eventTypeSelect.value = 'All';
            if (verificationSelect) verificationSelect.value = 'Needs Verification';
            if (duplicateSelect) duplicateSelect.value = 'All';
            hideError();
            loadReports(1);
        });
    }

    // Real-Time SocketIO Listener
    if (typeof io !== 'undefined') {
        const socket = io();
        socket.on('new_report', function () {
            loadSummary();
            loadReports(currentPage);
        });
        socket.on('weather_update', function () {
            loadSummary();
            loadReports(currentPage);
        });
    }

    // Initial Load
    loadSummary();
    loadReports(1);
});
