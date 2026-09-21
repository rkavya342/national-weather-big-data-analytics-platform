/**
 * reports_search.js
 * National Weather Intelligence Platform - Advanced Weather Report Search & Filtering
 */

document.addEventListener("DOMContentLoaded", function () {
    // Current pagination state
    let currentPage = 1;
    const perPage = 20;

    // DOM Elements
    const searchForm = document.getElementById('report-search-form');
    const keywordInput = document.getElementById('search-keyword');
    const eventTypeSelect = document.getElementById('search-event-type');
    const stateSelect = document.getElementById('search-state');
    const cityInput = document.getElementById('search-city');
    const sourceSelect = document.getElementById('search-source');
    const verificationSelect = document.getElementById('search-verification');
    const trustSelect = document.getElementById('search-trust');
    const duplicateSelect = document.getElementById('search-duplicate');
    const dateFromInput = document.getElementById('search-date-from');
    const dateToInput = document.getElementById('search-date-to');
    const sortBySelect = document.getElementById('search-sort-by');

    const applyBtn = document.getElementById('apply-search-filters');
    const clearBtn = document.getElementById('clear-search-filters');

    const countDisplay = document.getElementById('showing-count');
    const totalDisplay = document.getElementById('total-count');
    const tableBody = document.getElementById('reports-table-body');
    const emptyState = document.getElementById('reports-empty-state');
    const errorMessage = document.getElementById('search-error-alert');
    const errorText = document.getElementById('search-error-text');

    const paginationContainer = document.getElementById('pagination-container');

    // Modal Elements
    const detailsModalEl = document.getElementById('reportDetailsModal');
    let detailsModalInstance = null;
    if (detailsModalEl && typeof bootstrap !== 'undefined') {
        detailsModalInstance = new bootstrap.Modal(detailsModalEl);
    }

    // Helper: Escape HTML string to prevent XSS
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Helper: Format DateTime nicely
    function formatDateTime(dtStr) {
        if (!dtStr) return 'N/A';
        try {
            const d = new Date(dtStr);
            if (isNaN(d.getTime())) return dtStr;
            return d.toLocaleString('en-IN', {
                dateStyle: 'medium',
                timeStyle: 'short'
            });
        } catch (e) {
            return dtStr;
        }
    }

    // Helper: Validate Date Range
    function validateDateRange() {
        if (dateFromInput && dateToInput && dateFromInput.value && dateToInput.value) {
            if (dateFromInput.value > dateToInput.value) {
                showError("'Date From' cannot be later than 'Date To'.");
                return false;
            }
        }
        hideError();
        return true;
    }

    function showError(msg) {
        if (errorMessage && errorText) {
            errorText.textContent = msg;
            errorMessage.classList.remove('d-none');
        }
    }

    function hideError() {
        if (errorMessage) {
            errorMessage.classList.add('d-none');
        }
    }

    // Main fetch & render function
    async function performSearch(page = 1) {
        if (!validateDateRange()) return;

        currentPage = page;

        const params = new URLSearchParams({
            page: currentPage,
            per_page: perPage
        });

        if (keywordInput && keywordInput.value.trim()) params.append('keyword', keywordInput.value.trim());
        if (eventTypeSelect && eventTypeSelect.value !== 'All') params.append('event_type', eventTypeSelect.value);
        if (stateSelect && stateSelect.value !== 'All') params.append('state', stateSelect.value);
        if (cityInput && cityInput.value.trim()) params.append('city', cityInput.value.trim());
        if (sourceSelect && sourceSelect.value !== 'All') params.append('source', sourceSelect.value);
        if (verificationSelect && verificationSelect.value !== 'All') params.append('verification', verificationSelect.value);
        if (trustSelect && trustSelect.value !== 'All') params.append('trust_level', trustSelect.value);
        if (duplicateSelect && duplicateSelect.value !== 'All') params.append('duplicate_status', duplicateSelect.value);
        if (dateFromInput && dateFromInput.value) params.append('date_from', dateFromInput.value);
        if (dateToInput && dateToInput.value) params.append('date_to', dateToInput.value);
        if (sortBySelect && sortBySelect.value) params.append('sort_by', sortBySelect.value);

        try {
            const response = await fetch(`/api/reports/search?${params.toString()}`);
            const json = await response.json();

            if (json.status === 'success' && json.data) {
                renderTable(json.data.reports || []);
                renderPagination(json.data.page, json.data.total_pages, json.data.total);
                updateCounts(json.data.reports ? json.data.reports.length : 0, json.data.total || 0);
            } else {
                showError(json.message || "Failed to search reports.");
                renderTable([]);
                updateCounts(0, 0);
            }
        } catch (err) {
            console.error("Search API Error:", err);
            showError("Network error while searching weather reports.");
            renderTable([]);
            updateCounts(0, 0);
        }
    }

    // Update Showing/Total Counts
    function updateCounts(showing, total) {
        if (countDisplay) countDisplay.textContent = showing;
        if (totalDisplay) totalDisplay.textContent = total;
    }

    // Render Table Rows
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

            // Source badge styling
            const src = report.source || 'Citizen Report';
            const srcClass = src === 'Citizen Report' ? 'bg-primary-subtle text-primary-emphasis' :
                             src.includes('API') ? 'bg-info-subtle text-info-emphasis' : 'bg-secondary-subtle text-dark';

            // Trust badge styling
            const trustScore = report.trust_score !== null && report.trust_score !== undefined ? Number(report.trust_score) : 50.0;
            let trustBadge = 'bg-danger';
            let trustLabel = 'Low Trust';
            if (trustScore >= 80.0) {
                trustBadge = 'bg-success';
                trustLabel = 'High Trust';
            } else if (trustScore >= 50.0) {
                trustBadge = 'bg-warning text-dark';
                trustLabel = 'Medium Trust';
            }

            // Verification result badge
            const vRes = report.verification_result || report.verification_status || 'Unverified';
            let vBadge = '<span class="badge bg-secondary px-2 py-1">Unverified</span>';
            if (vRes === 'Likely Consistent') {
                vBadge = '<span class="badge bg-success px-2 py-1"><i class="bi bi-check-circle-fill me-1"></i>Likely Consistent</span>';
            } else if (vRes === 'Needs Verification') {
                vBadge = '<span class="badge bg-warning text-dark px-2 py-1"><i class="bi bi-exclamation-circle-fill me-1"></i>Needs Verification</span>';
            } else if (vRes === 'Suspicious') {
                vBadge = '<span class="badge bg-danger px-2 py-1"><i class="bi bi-shield-x me-1"></i>Suspicious</span>';
            }

            // Duplicate status badge
            const dupStat = report.duplicate_status || (report.is_duplicate ? 'Potential Duplicate' : 'Unique');
            let dupBadge = '<span class="badge bg-info-subtle text-info-emphasis px-2 py-1">Unique</span>';
            if (dupStat === 'Potential Duplicate') {
                dupBadge = '<span class="badge bg-danger px-2 py-1"><i class="bi bi-files me-1"></i>Duplicate</span>';
            } else if (dupStat === 'Related Report') {
                dupBadge = '<span class="badge bg-warning-subtle text-dark px-2 py-1"><i class="bi bi-diagram-3-fill me-1"></i>Related</span>';
            }

            const aiConf = report.ai_confidence !== null && report.ai_confidence !== undefined ? Number(report.ai_confidence).toFixed(1) : 'N/A';
            const locationStr = `${escapeHtml(report.city || 'N/A')}${report.state ? ', <small class="text-muted">' + escapeHtml(report.state) + '</small>' : ''}`;
            const dtStr = formatDateTime(report.report_datetime || report.created_at);

            // Action buttons
            let mapBtn = '';
            if (report.latitude && report.longitude) {
                mapBtn = `<a href="/dashboard?lat=${report.latitude}&lng=${report.longitude}&report_id=${report.id}" class="btn btn-outline-success btn-sm me-1" title="View on Map"><i class="bi bi-map-fill"></i> Map</a>`;
            }

            tr.innerHTML = `
                <td><span class="fw-bold">#${report.id}</span></td>
                <td><span class="badge ${srcClass}">${escapeHtml(src)}</span></td>
                <td><span class="badge bg-info-subtle text-info-emphasis">${escapeHtml(report.event_type || 'General')}</span></td>
                <td>${locationStr}</td>
                <td><small class="text-muted">${dtStr}</small></td>
                <td>${vBadge}</td>
                <td>
                    <span class="badge ${trustBadge} px-2 py-1 mb-1 d-inline-block">${trustLabel}</span>
                    <div class="fw-bold text-dark fs-7">${trustScore.toFixed(1)}%</div>
                </td>
                <td>${dupBadge}</td>
                <td><span class="fw-semibold text-secondary">${aiConf}%</span></td>
                <td class="text-nowrap">
                    <button type="button" class="btn btn-outline-info btn-sm me-1 btn-view-details" data-id="${report.id}" title="View Full Details">
                        <i class="bi bi-eye-fill me-1"></i> Details
                    </button>
                    ${mapBtn}
                    <a href="/analyze_report/${report.id}" class="btn btn-outline-primary btn-sm fw-semibold" title="Run AI Re-Analysis">
                        <i class="bi bi-cpu"></i>
                    </a>
                </td>
            `;

            tableBody.appendChild(tr);
        });

        // Attach event listeners to "Details" buttons
        document.querySelectorAll('.btn-view-details').forEach(btn => {
            btn.addEventListener('click', function () {
                const rId = this.getAttribute('data-id');
                openDetailsModal(rId);
            });
        });
    }

    // Render Pagination Controls
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
        prevLi.innerHTML = `<a class="page-link" href="#" aria-label="Previous">&laquo; Prev</a>`;
        if (page > 1) {
            prevLi.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page - 1);
            });
        }
        ul.appendChild(prevLi);

        // Page Number Links (Window of 5 pages max)
        const startPage = Math.max(1, page - 2);
        const endPage = Math.min(totalPages, startPage + 4);

        for (let i = startPage; i <= endPage; i++) {
            const pageLi = document.createElement('li');
            pageLi.className = `page-item ${i === page ? 'active' : ''}`;
            pageLi.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            if (i !== page) {
                const targetPage = i;
                pageLi.addEventListener('click', (e) => {
                    e.preventDefault();
                    performSearch(targetPage);
                });
            }
            ul.appendChild(pageLi);
        }

        // Next Button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${page >= totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#" aria-label="Next">Next &raquo;</a>`;
        if (page < totalPages) {
            nextLi.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page + 1);
            });
        }
        ul.appendChild(nextLi);

        nav.appendChild(ul);
        paginationContainer.appendChild(nav);
    }

    // Fetch and display Report Details Modal
    async function openDetailsModal(reportId) {
        try {
            const res = await fetch(`/api/reports/${reportId}`);
            const json = await res.json();
            if (json.status === 'success' && json.report) {
                const r = json.report;
                
                const setM = (id, val) => {
                    const el = document.getElementById(id);
                    if (el) el.textContent = val !== null && val !== undefined && val !== '' ? val : 'N/A';
                };

                setM('modal-report-id', `#${r.id}`);
                setM('modal-source', r.source || 'Citizen Report');
                setM('modal-event-type', r.event_type || 'General');
                setM('modal-location', `${r.city || 'N/A'}${r.state ? ', ' + r.state : ''}`);
                setM('modal-coordinates', r.latitude && r.longitude ? `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}` : 'N/A');
                setM('modal-datetime', formatDateTime(r.report_datetime || r.created_at));
                setM('modal-report-text', r.report_text || 'No text provided.');
                
                setM('modal-verification-result', r.verification_result || r.verification_status || 'Unverified');
                setM('modal-verification-score', r.verification_score !== null ? `${Number(r.verification_score).toFixed(1)}%` : 'N/A');
                setM('modal-verification-reason', r.verification_reason || 'N/A');
                
                setM('modal-trust-score', r.trust_score !== null ? `${Number(r.trust_score).toFixed(1)} / 100` : 'N/A');
                setM('modal-trust-reason', r.trust_reason || 'N/A');

                setM('modal-duplicate-status', r.duplicate_status || (r.is_duplicate ? 'Potential Duplicate' : 'Unique'));
                setM('modal-duplicate-similarity', r.duplicate_similarity_score !== null ? `${Number(r.duplicate_similarity_score).toFixed(1)}%` : 'N/A');
                setM('modal-duplicate-reason', r.duplicate_reason || 'N/A');

                setM('modal-ai-confidence', r.ai_confidence !== null ? `${Number(r.ai_confidence).toFixed(1)}%` : 'N/A');

                // Media links
                const imgContainer = document.getElementById('modal-image-container');
                if (imgContainer) {
                    if (r.image_url && r.image_url.trim()) {
                        imgContainer.innerHTML = `<img src="${escapeHtml(r.image_url)}" class="img-fluid rounded border shadow-sm style="max-height: 250px;">`;
                    } else {
                        imgContainer.innerHTML = '<span class="text-muted small">No image attachment</span>';
                    }
                }

                const srcUrlEl = document.getElementById('modal-source-url');
                if (srcUrlEl) {
                    if (r.source_url && r.source_url.trim()) {
                        srcUrlEl.href = r.source_url;
                        srcUrlEl.textContent = r.source_url;
                        srcUrlEl.parentElement.classList.remove('d-none');
                    } else {
                        srcUrlEl.parentElement.classList.add('d-none');
                    }
                }

                if (detailsModalInstance) {
                    detailsModalInstance.show();
                }
            } else {
                alert(json.message || "Failed to load report details.");
            }
        } catch (e) {
            console.error("Failed to load details:", e);
            alert("Error fetching report details.");
        }
    }

    // Filter event listeners
    if (applyBtn) {
        applyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            performSearch(1);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (keywordInput) keywordInput.value = '';
            if (eventTypeSelect) eventTypeSelect.value = 'All';
            if (stateSelect) stateSelect.value = 'All';
            if (cityInput) cityInput.value = '';
            if (sourceSelect) sourceSelect.value = 'All';
            if (verificationSelect) verificationSelect.value = 'All';
            if (trustSelect) trustSelect.value = 'All';
            if (duplicateSelect) duplicateSelect.value = 'All';
            if (dateFromInput) dateFromInput.value = '';
            if (dateToInput) dateToInput.value = '';
            if (sortBySelect) sortBySelect.value = 'date_desc';
            hideError();
            performSearch(1);
        });
    }

    if (sortBySelect) {
        sortBySelect.addEventListener('change', () => {
            performSearch(1);
        });
    }

    // SocketIO Real-Time Integration
    if (typeof io !== 'undefined') {
        const socket = io();
        socket.on('new_report', function () {
            performSearch(currentPage);
        });
        socket.on('weather_update', function () {
            performSearch(currentPage);
        });
    }

    // Initial Load
    performSearch(1);
});
