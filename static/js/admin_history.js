/**
 * admin_history.js
 * National Weather Intelligence Platform - Admin Activity Audit Log
 */

document.addEventListener("DOMContentLoaded", function () {
    let currentPage = 1;
    const perPage = 20;

    const showingCount = document.getElementById('history-showing-count');
    const totalCount = document.getElementById('history-total-count');
    const tableBody = document.getElementById('history-table-body');
    const emptyState = document.getElementById('history-empty-state');
    const paginationContainer = document.getElementById('history-pagination-container');

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

    async function loadHistory(page = 1) {
        currentPage = page;

        try {
            const res = await fetch(`/api/admin/history?page=${currentPage}&per_page=${perPage}`);
            const json = await res.json();

            if (json.status === 'success' && json.data) {
                renderTable(json.data.actions || []);
                renderPagination(json.data.page, json.data.total_pages, json.data.total);
                if (showingCount) showingCount.textContent = json.data.actions ? json.data.actions.length : 0;
                if (totalCount) totalCount.textContent = json.data.total || 0;
            } else {
                renderTable([]);
            }
        } catch (e) {
            console.error("Failed to load audit history:", e);
            renderTable([]);
        }
    }

    function renderTable(actions) {
        if (!tableBody) return;
        tableBody.innerHTML = '';

        if (!actions || actions.length === 0) {
            if (emptyState) emptyState.classList.remove('d-none');
            return;
        }

        if (emptyState) emptyState.classList.add('d-none');

        actions.forEach(act => {
            const tr = document.createElement('tr');

            const actType = act.action_type || 'Updated Verification';
            let actBadge = 'bg-primary';
            if (actType.includes('Suspicious')) actBadge = 'bg-danger';
            else if (actType.includes('Verified')) actBadge = 'bg-success';
            else if (actType.includes('Request')) actBadge = 'bg-warning text-dark';

            const newV = act.new_verification || 'N/A';
            let vBadge = 'bg-secondary';
            if (newV === 'Verified' || newV === 'Likely Consistent') vBadge = 'bg-success';
            else if (newV === 'Suspicious') vBadge = 'bg-danger';
            else if (newV === 'Needs Verification') vBadge = 'bg-warning text-dark';

            tr.innerHTML = `
                <td><span class="fw-bold">#${act.id}</span></td>
                <td><a href="/admin" class="fw-bold text-decoration-none">#${act.report_id}</a></td>
                <td><span class="badge ${actBadge}">${escapeHtml(actType)}</span></td>
                <td><span class="badge bg-secondary-subtle text-dark">${escapeHtml(act.previous_verification || 'Unverified')}</span></td>
                <td><span class="badge ${vBadge}">${escapeHtml(newV)}</span></td>
                <td><small class="text-dark d-block text-wrap" style="max-width: 320px;">${escapeHtml(act.reason || 'No audit notes provided.')}</small></td>
                <td><span class="fw-bold text-dark"><i class="bi bi-person-fill me-1"></i>${escapeHtml(act.performed_by || 'Admin')}</span></td>
                <td><small class="text-muted">${formatDT(act.action_datetime)}</small></td>
            `;

            tableBody.appendChild(tr);
        });
    }

    function renderPagination(page, totalPages, total) {
        if (!paginationContainer) return;
        paginationContainer.innerHTML = '';

        if (totalPages <= 1) return;

        const nav = document.createElement('nav');
        const ul = document.createElement('ul');
        ul.className = 'pagination pagination-sm mb-0';

        // Prev
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${page <= 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#">&laquo; Prev</a>`;
        if (page > 1) {
            prevLi.addEventListener('click', (e) => {
                e.preventDefault();
                loadHistory(page - 1);
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
                    loadHistory(targetPage);
                });
            }
            ul.appendChild(li);
        }

        // Next
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${page >= totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#">Next &raquo;</a>`;
        if (page < totalPages) {
            nextLi.addEventListener('click', (e) => {
                e.preventDefault();
                loadHistory(page + 1);
            });
        }
        ul.appendChild(nextLi);

        nav.appendChild(ul);
        paginationContainer.appendChild(nav);
    }

    loadHistory(1);
});
