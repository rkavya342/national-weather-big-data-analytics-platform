/**
 * advanced_analytics.js
 * National Weather Intelligence Platform - Advanced Weather Analytics & Charts
 */

document.addEventListener("DOMContentLoaded", function () {
    // Dictionary to hold active Chart.js instances so they can be properly destroyed before re-render
    const chartInstances = {};

    // Color palettes for visual consistency
    const palette = {
        primary: '#0d6efd',
        secondary: '#6c757d',
        success: '#198754',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#0dcaf0',
        teal: '#20c997',
        orange: '#fd7e14',
        indigo: '#6610f2',
        purple: '#6f42c1',
        pink: '#d63384',
        chartColors: [
            '#0d6efd', '#0dcaf0', '#198754', '#ffc107', '#dc3545',
            '#fd7e14', '#20c997', '#6610f2', '#6f42c1', '#d63384',
            '#6c757d', '#17a2b8', '#28a745', '#ffc107', '#e83e8c'
        ]
    };

    // DOM Elements
    const dateFromInput = document.getElementById('analytics-date-from');
    const dateToInput = document.getElementById('analytics-date-to');
    const eventTypeSelect = document.getElementById('analytics-event-type');
    const stateSelect = document.getElementById('analytics-state');
    const sourceSelect = document.getElementById('analytics-source');
    const applyBtn = document.getElementById('apply-analytics-filters');
    const resetBtn = document.getElementById('reset-analytics-filters');

    // Helper: Safely destroy existing chart instance
    function destroyChart(chartId) {
        if (chartInstances[chartId]) {
            chartInstances[chartId].destroy();
            delete chartInstances[chartId];
        }
    }

    // Helper: Format labels nicely
    function formatLabel(str) {
        if (!str) return 'Unknown';
        return str.toString().replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    // Main fetch & render function
    async function loadAnalytics() {
        const queryParams = new URLSearchParams();

        if (dateFromInput && dateFromInput.value) queryParams.append('date_from', dateFromInput.value);
        if (dateToInput && dateToInput.value) queryParams.append('date_to', dateToInput.value);
        if (eventTypeSelect && eventTypeSelect.value && eventTypeSelect.value !== 'All') queryParams.append('event_type', eventTypeSelect.value);
        if (stateSelect && stateSelect.value && stateSelect.value !== 'All') queryParams.append('state', stateSelect.value);
        if (sourceSelect && sourceSelect.value && sourceSelect.value !== 'All') queryParams.append('source', sourceSelect.value);

        const url = `/api/analytics?${queryParams.toString()}`;

        try {
            const response = await fetch(url);
            const data = await response.json();

            if (data.status === 'success' && (data.data || data.analytics)) {
                const payload = data.data || data.analytics;
                const summary = payload.summary || payload.overall_summary || {};
                
                renderSummaryCards(summary);
                renderEventsByTypeChart(payload.events_by_type);
                renderEventsByStateChart(payload.events_by_state);
                renderReportsOverTimeChart(payload.reports_over_time);
                renderReportsBySourceChart(payload.source_distribution);
                renderVerificationStatusChart(payload.verification_status || payload.verification_distribution);
                renderTrustDistributionChart(payload.trust_distribution || payload.trust_score_distribution);
                renderTopCitiesChart(payload.top_cities);
                renderTopSourcesTrustChart(payload.top_sources_trust || payload.top_sources);
            } else {
                console.warn("Analytics API returned error or empty state:", data);
            }
        } catch (error) {
            console.error("Failed to fetch analytics data:", error);
        }
    }

    // 1. Render Summary Cards
    function renderSummaryCards(summary) {
        if (!summary) return;
        
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val !== null && val !== undefined ? val : 0;
        };

        setVal('adv-total-reports', summary.total_reports || 0);
        setVal('adv-total-obs', summary.total_weather_observations || 0);
        setVal('adv-verified-reports', summary.verified_reports || 0);
        setVal('adv-suspicious-reports', summary.suspicious_reports || 0);
        setVal('adv-needs-verification', summary.needs_verification || 0);
        setVal('adv-total-states', summary.total_states || 0);
        
        const avgTrust = summary.average_trust_score !== undefined ? Number(summary.average_trust_score).toFixed(1) : '0.0';
        setVal('adv-avg-trust', `${avgTrust} / 100`);
    }

    // 2. Events by Type (Bar Chart)
    function renderEventsByTypeChart(items) {
        const canvas = document.getElementById('advEventsByTypeChart');
        if (!canvas) return;
        destroyChart('advEventsByTypeChart');

        const labels = (items || []).map(i => formatLabel(i.event_type));
        const counts = (items || []).map(i => i.count);

        chartInstances['advEventsByTypeChart'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Event Count',
                    data: counts.length ? counts : [0],
                    backgroundColor: palette.chartColors.slice(0, Math.max(labels.length, 1)),
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 3. Events by State (Bar Chart)
    function renderEventsByStateChart(items) {
        const canvas = document.getElementById('advEventsByStateChart');
        if (!canvas) return;
        destroyChart('advEventsByStateChart');

        const labels = (items || []).map(i => formatLabel(i.state));
        const counts = (items || []).map(i => i.count);

        chartInstances['advEventsByStateChart'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Reports & Events',
                    data: counts.length ? counts : [0],
                    backgroundColor: palette.primary,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 } },
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 4. Reports Over Time (Line Chart)
    function renderReportsOverTimeChart(items) {
        const canvas = document.getElementById('advReportsOverTimeChart');
        if (!canvas) return;
        destroyChart('advReportsOverTimeChart');

        const labels = (items || []).map(i => i.report_date || i.date || 'Unknown');
        const counts = (items || []).map(i => i.count);

        chartInstances['advReportsOverTimeChart'] = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Reports Count',
                    data: counts.length ? counts : [0],
                    borderColor: palette.primary,
                    backgroundColor: 'rgba(13, 110, 253, 0.15)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 5. Reports by Source (Doughnut Chart)
    function renderReportsBySourceChart(items) {
        const canvas = document.getElementById('advReportsBySourceChart');
        if (!canvas) return;
        destroyChart('advReportsBySourceChart');

        const labels = (items || []).map(i => formatLabel(i.source));
        const counts = (items || []).map(i => i.count);

        chartInstances['advReportsBySourceChart'] = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    data: counts.length ? counts : [0],
                    backgroundColor: palette.chartColors.slice(0, Math.max(labels.length, 1))
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // 6. Verification Status Distribution (Pie Chart)
    function renderVerificationStatusChart(items) {
        const canvas = document.getElementById('advVerificationStatusChart');
        if (!canvas) return;
        destroyChart('advVerificationStatusChart');

        const labels = (items || []).map(i => formatLabel(i.status || i.verification_result || i.verification_status));
        const counts = (items || []).map(i => i.count);

        const statusColors = (items || []).map(i => {
            const st = (i.status || i.verification_result || '').toLowerCase();
            if (st.includes('consistent') || st.includes('verified')) return palette.success;
            if (st.includes('suspicious')) return palette.danger;
            if (st.includes('needs')) return palette.warning;
            return palette.secondary;
        });

        chartInstances['advVerificationStatusChart'] = new Chart(canvas, {
            type: 'pie',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    data: counts.length ? counts : [0],
                    backgroundColor: statusColors.length ? statusColors : [palette.secondary]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // 7. Source Trust Score Distribution (Bar Chart)
    function renderTrustDistributionChart(items) {
        const canvas = document.getElementById('advTrustDistributionChart');
        if (!canvas) return;
        destroyChart('advTrustDistributionChart');

        const labels = (items || []).map(i => formatLabel(i.label || i.trust_category));
        const counts = (items || []).map(i => i.count);

        chartInstances['advTrustDistributionChart'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Reports',
                    data: counts.length ? counts : [0],
                    backgroundColor: [palette.success, palette.info, palette.warning, palette.danger],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 8. Top 10 Affected Cities (Horizontal Bar Chart)
    function renderTopCitiesChart(items) {
        const canvas = document.getElementById('advTopCitiesChart');
        if (!canvas) return;
        destroyChart('advTopCitiesChart');

        const labels = (items || []).map(i => `${formatLabel(i.city)}${i.state ? ' (' + formatLabel(i.state) + ')' : ''}`);
        const counts = (items || []).map(i => i.count);

        chartInstances['advTopCitiesChart'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Report Count',
                    data: counts.length ? counts : [0],
                    backgroundColor: palette.teal,
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    // 9. Top Sources by Average Trust Score (Horizontal Bar Chart)
    function renderTopSourcesTrustChart(items) {
        const canvas = document.getElementById('advTopSourcesTrustChart');
        if (!canvas) return;
        destroyChart('advTopSourcesTrustChart');

        const labels = (items || []).map(i => formatLabel(i.source));
        const trustScores = (items || []).map(i => Number(i.avg_trust || 0).toFixed(1));

        chartInstances['advTopSourcesTrustChart'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    label: 'Avg Trust Score (0-100)',
                    data: trustScores.length ? trustScores : [0],
                    backgroundColor: palette.orange,
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { beginAtZero: true, max: 100, ticks: { precision: 0 } }
                }
            }
        });
    }

    // Event Listeners for Filters
    if (applyBtn) {
        applyBtn.addEventListener('click', function (e) {
            e.preventDefault();
            loadAnalytics();
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (dateFromInput) dateFromInput.value = '';
            if (dateToInput) dateToInput.value = '';
            if (eventTypeSelect) eventTypeSelect.value = 'All';
            if (stateSelect) stateSelect.value = 'All';
            if (sourceSelect) sourceSelect.value = 'All';
            loadAnalytics();
        });
    }

    // Listen for Real-Time Socket.IO Updates if available
    if (typeof io !== 'undefined') {
        const socket = io();
        socket.on('weather_update', function () {
            loadAnalytics();
        });
        socket.on('new_report', function () {
            loadAnalytics();
        });
    }

    // Initial Load
    loadAnalytics();
});
