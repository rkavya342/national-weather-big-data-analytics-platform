/**
 * National Weather Intelligence Platform
 * Real-Time Dashboard Updates & Socket.IO Listener Controller
 */

(function () {
    if (window.__socketio_listener_initialized) return;
    window.__socketio_listener_initialized = true;

    document.addEventListener("DOMContentLoaded", function () {
        if (typeof io === "undefined") {
            console.warn("Socket.IO client library not loaded.");
            return;
        }

        // Initialize Socket.IO connection
        const socket = io({
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000
        });

        const connBadge = document.getElementById("live-connection-badge");

        function updateConnectionStatus(isConnected) {
            if (!connBadge) return;
            if (isConnected) {
                connBadge.className = "badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2 ms-2";
                connBadge.innerHTML = '<i class="bi bi-circle-fill me-1 text-success" style="font-size: 0.65rem;"></i> Live Connection: Connected';
            } else {
                connBadge.className = "badge bg-danger-subtle text-danger border border-danger-subtle rounded-pill px-3 py-2 ms-2";
                connBadge.innerHTML = '<i class="bi bi-circle-fill me-1 text-danger" style="font-size: 0.65rem;"></i> Live Connection: Disconnected';
            }
        }

        socket.on("connect", function () {
            console.log("Socket.IO connected to backend real-time server.");
            updateConnectionStatus(true);
        });

        socket.on("disconnect", function () {
            console.warn("Socket.IO connection lost.");
            updateConnectionStatus(false);
        });

        // Function to refresh dashboard summary counters & tables asynchronously
        function refreshDashboardData() {
            fetch("/api/dashboard-summary")
                .then(res => res.json())
                .then(data => {
                    if (data.status === "success") {
                        console.log("Real-time summary payload received:", data);

                        // Update Multi-Source Cards if present
                        if (data.multi_source_summary) {
                            const ms = data.multi_source_summary;
                            updateText("ms-total-reports", ms.total_reports);
                            updateText("ms-official-api", ms.official_api_reports);
                            updateText("ms-citizen-reports", ms.citizen_reports);
                            updateText("ms-social-media", ms.social_media_reports);
                            updateText("ms-news-reports", ms.news_reports);
                            updateText("ms-public-dataset", ms.public_dataset_reports);
                        }

                        // Update Verification Summary Counters if present
                        if (data.verification_summary) {
                            const vs = data.verification_summary;
                            updateText("summary-total-citizen", vs["Total Citizen Reports"]);
                        }

                        // Update Trust Summary Cards if present
                        if (data.trust_summary) {
                            const ts = data.trust_summary;
                            updateText("trust-avg-score", (ts.avg_trust || 0).toFixed(1) + "%");
                            updateText("trust-high-count", ts.high_trust_count);
                            updateText("trust-medium-count", ts.medium_trust_count);
                            updateText("trust-low-count", ts.low_trust_count);
                        }
                    }
                })
                .catch(err => console.error("Error refreshing dashboard data:", err));

            // Refresh spatial Leaflet map markers if map controller is mounted
            if (typeof window.reloadMapMarkers === "function") {
                window.reloadMapMarkers();
            }
        }

        function updateText(elementId, val) {
            const el = document.getElementById(elementId);
            if (el && val !== undefined && val !== null) {
                el.textContent = val;
            }
        }

        // Listen for real-time 'weather_update' event
        socket.on("weather_update", function (payload) {
            console.log("Real-time Socket.IO event received: 'weather_update'", payload);
            refreshDashboardData();
        });

        // Listen for real-time 'new_report' event
        socket.on("new_report", function (payload) {
            console.log("Real-time Socket.IO event received: 'new_report'", payload);
            refreshDashboardData();
        });
    });
})();
