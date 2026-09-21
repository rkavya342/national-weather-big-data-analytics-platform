/**
 * National Weather Intelligence Platform
 * Interactive India Weather Map & Spatial Location Intelligence (Leaflet.js)
 */

document.addEventListener("DOMContentLoaded", function () {
    const mapContainer = document.getElementById("india-weather-map") || document.getElementById("india-live-event-map");
    if (!mapContainer) return;

    const targetId = mapContainer.id;

    // Initialize Leaflet map centered on India
    const map = L.map(targetId, {
        center: [20.5937, 78.9629],
        zoom: 5,
        zoomControl: true
    });

    // Invalidate map size after DOM render to ensure tile layout renders immediately
    setTimeout(function() {
        if (map) map.invalidateSize();
    }, 250);

    // Add OpenStreetMap Tile Layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(map);

    // Marker Layer Group
    const markersLayer = L.layerGroup().addTo(map);

    let allMapRecords = [];

    // Color palette mapping per weather event type
    function getEventColor(eventType) {
        switch (eventType) {
            case "Flood Risk":
                return "#dc3545"; // Dark Red
            case "Heavy Rainfall":
                return "#0d6efd"; // Primary Blue
            case "Thunderstorm":
                return "#ffc107"; // Warning Amber
            case "Heatwave":
                return "#fd7e14"; // Orange/Red
            case "Fog":
                return "#6c757d"; // Secondary Grey
            case "Dust Storm":
                return "#856404"; // Dark Yellow/Brown
            case "Strong Wind":
                return "#212529"; // Dark
            case "Normal Weather":
            default:
                return "#198754"; // Green
        }
    }

    // Helper to escape HTML to prevent XSS
    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Build rich HTML popup content for each marker
    function buildPopupContent(r) {
        const city = escapeHtml(r.city || "Unknown Location");
        const state = escapeHtml(r.state || "India");
        const source = escapeHtml(r.source || "Citizen Report");
        const eventType = escapeHtml(r.event_type || "Normal Weather");
        const timeStr = r.report_datetime || r.recorded_at || r.created_at || "--";
        const eventColor = getEventColor(r.event_type);

        let content = `
            <div style="min-width: 220px; font-family: sans-serif;">
                <div style="border-bottom: 2px solid ${eventColor}; padding-bottom: 4px; margin-bottom: 8px;">
                    <span style="background-color: ${eventColor}; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; float: right;">
                        ${eventType}
                    </span>
                    <h6 style="margin: 0; font-weight: bold; color: #212529;">${city}, ${state}</h6>
                </div>
                <div style="font-size: 0.825rem; color: #495057;">
                    <div style="margin-bottom: 3px;"><strong>Source:</strong> ${source}</div>
        `;

        if (r.temperature !== undefined && r.temperature !== null) {
            content += `<div style="margin-bottom: 3px;"><strong>Temperature:</strong> ${r.temperature.toFixed(1)}°C</div>`;
        }
        if (r.humidity !== undefined && r.humidity !== null) {
            content += `<div style="margin-bottom: 3px;"><strong>Humidity:</strong> ${r.humidity}%</div>`;
        }
        if (r.wind_speed !== undefined && r.wind_speed !== null) {
            content += `<div style="margin-bottom: 3px;"><strong>Wind Speed:</strong> ${r.wind_speed} m/s</div>`;
        }

        if (r.verification_result) {
            let vClass = "#6c757d";
            if (r.verification_result === "Likely Consistent") vClass = "#198754";
            else if (r.verification_result === "Suspicious") vClass = "#dc3545";

            content += `
                <div style="margin-bottom: 3px;">
                    <strong>Verification:</strong> 
                    <span style="color: ${vClass}; font-weight: bold;">${escapeHtml(r.verification_result)}</span>
                </div>
            `;
        }

        if (r.trust_score !== undefined && r.trust_score !== null) {
            let tColor = "#198754";
            if (r.trust_score < 50) tColor = "#dc3545";
            else if (r.trust_score < 80) tColor = "#b58105";

            content += `
                <div style="margin-bottom: 3px;">
                    <strong>Trust Score:</strong> 
                    <span style="color: ${tColor}; font-weight: bold;">${r.trust_score.toFixed(1)}%</span>
                </div>
            `;
        }

        if (r.report_text) {
            const snippet = escapeHtml(r.report_text.length > 100 ? r.report_text.substring(0, 100) + "..." : r.report_text);
            content += `<div style="margin-top: 6px; padding: 4px 6px; background-color: #f8f9fa; border-radius: 4px; font-style: italic; font-size: 0.775rem;">"${snippet}"</div>`;
        }

        content += `
                <div style="margin-top: 6px; font-size: 0.725rem; color: #6c757d;">
                    <i class="bi bi-clock"></i> ${escapeHtml(timeStr)}
                </div>
            </div>
        `;

        return content;
    }

    // Populate state filter dropdown options dynamically from returned data
    function populateStateFilterOptions(records) {
        const stateSelect = document.getElementById("map-state-filter");
        if (!stateSelect) return;

        const currentVal = stateSelect.value;
        const states = Array.from(new Set(records.map(r => r.state).filter(Boolean))).sort();

        // Keep 'All' option, clear others
        stateSelect.innerHTML = '<option value="All">All States</option>';

        states.forEach(st => {
            const opt = document.createElement("option");
            opt.value = st;
            opt.textContent = st;
            if (st === currentVal) opt.selected = true;
            stateSelect.appendChild(opt);
        });
    }

    // Render geographic markers on map
    function renderMarkers(records) {
        markersLayer.clearLayers();

        records.forEach(r => {
            if (r.latitude && r.longitude && !isNaN(r.latitude) && !isNaN(r.longitude)) {
                const color = getEventColor(r.event_type);

                const marker = L.circleMarker([r.latitude, r.longitude], {
                    radius: 8,
                    fillColor: color,
                    color: "#ffffff",
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85
                });

                marker.bindPopup(buildPopupContent(r));
                markersLayer.addLayer(marker);
            }
        });
    }

    // Apply interactive map filters & update summary counters
    function applyMapFilters() {
        const eventVal = document.getElementById("map-event-filter") ? document.getElementById("map-event-filter").value : "All";
        const stateVal = document.getElementById("map-state-filter") ? document.getElementById("map-state-filter").value : "All";
        const sourceVal = document.getElementById("map-source-filter") ? document.getElementById("map-source-filter").value : "All";
        const verifVal = document.getElementById("map-verification-filter") ? document.getElementById("map-verification-filter").value : "All";
        const trustVal = document.getElementById("map-trust-filter") ? document.getElementById("map-trust-filter").value : "All";

        const filtered = allMapRecords.filter(r => {
            // Event Filter
            if (eventVal !== "All" && r.event_type !== eventVal) return false;

            // State Filter
            if (stateVal !== "All" && r.state !== stateVal) return false;

            // Source Filter
            if (sourceVal !== "All") {
                if (sourceVal === "Official Weather API" && r.source !== "Official Weather API" && r.source !== "OpenWeatherMap API") return false;
                else if (sourceVal !== "Official Weather API" && r.source !== sourceVal) return false;
            }

            // Verification Filter
            if (verifVal !== "All" && (r.verification_result || "Unverified") !== verifVal) return false;

            // Trust Level Filter
            if (trustVal !== "All") {
                const score = r.trust_score !== undefined && r.trust_score !== null ? r.trust_score : 50;
                if (trustVal === "High Trust" && score < 80.0) return false;
                if (trustVal === "Medium Trust" && (score < 50.0 || score >= 80.0)) return false;
                if (trustVal === "Low Trust" && score >= 50.0) return false;
            }

            return true;
        });

        renderMarkers(filtered);

        // Update Map Summary Header Counters
        const totalCountBadge = document.getElementById("mapped-count-badge") || document.getElementById("map-total-markers-badge");
        const eventsCountBadge = document.getElementById("mapped-events-badge");
        const statesCountBadge = document.getElementById("mapped-states-badge");

        if (totalCountBadge) {
            totalCountBadge.textContent = totalCountBadge.id === "map-total-markers-badge" ? `${filtered.length} Markers` : filtered.length;
        }

        if (eventsCountBadge) {
            const activeEvents = new Set(filtered.map(r => r.event_type).filter(Boolean));
            eventsCountBadge.textContent = activeEvents.size;
        }

        if (statesCountBadge) {
            const activeStates = new Set(filtered.map(r => r.state).filter(Boolean));
            statesCountBadge.textContent = activeStates.size;
        }

        if (map) {
            setTimeout(function() { map.invalidateSize(); }, 100);
        }
    }

    // Fetch spatial weather records from backend API /api/map-data
    function fetchAndRenderMapData() {
        fetch("/api/map-data")
            .then(res => res.json())
            .then(data => {
                if (data.status === "success" && Array.isArray(data.records)) {
                    allMapRecords = data.records;
                    populateStateFilterOptions(allMapRecords);
                    applyMapFilters();
                }
            })
            .catch(err => console.error("Error fetching map geographic records:", err));
    }

    // Attach event listeners to filter dropdowns
    ["map-event-filter", "map-state-filter", "map-source-filter", "map-verification-filter", "map-trust-filter"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("change", applyMapFilters);
    });

    // Attach listener to Reset Filters button
    const resetBtn = document.getElementById("reset-map-filters-btn") || document.getElementById("reset-map-filters");
    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            ["map-event-filter", "map-state-filter", "map-source-filter", "map-verification-filter", "map-trust-filter"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = "All";
            });
            applyMapFilters();
        });
    }

    // Expose reload function globally for real-time SocketIO updates
    window.reloadMapMarkers = fetchAndRenderMapData;

    // Map Click Listener for instant geographic weather lookup anywhere on the map
    let tempClickMarker = null;

    map.on("click", function (e) {
        const lat = e.latlng.lat.toFixed(4);
        const lon = e.latlng.lng.toFixed(4);

        if (tempClickMarker) {
            markersLayer.removeLayer(tempClickMarker);
        }

        tempClickMarker = L.marker([lat, lon], {
            icon: L.divIcon({
                className: "custom-click-pin",
                html: `<div style="background-color: #0d6efd; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 8px rgba(13,110,253,0.8);"></div>`,
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            })
        });

        markersLayer.addLayer(tempClickMarker);

        tempClickMarker.bindPopup(`
            <div style="min-width: 200px; text-align: center; font-family: sans-serif; padding: 4px;">
                <span style="background-color: #0d6efd; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.725rem; font-weight: bold;" class="d-inline-block mb-2">
                    Map Click Weather Lookup
                </span>
                <div class="mb-1 text-muted small">Coords: (${lat}, ${lon})</div>
                <div class="spinner-border spinner-border-sm text-primary my-2" role="status"></div>
                <div class="text-muted small">Querying OpenWeatherMap API...</div>
            </div>
        `).openPopup();

        fetch(`/api/weather/coords?lat=${lat}&lon=${lon}`)
            .then(res => res.json())
            .then(res => {
                if (res.success && res.data) {
                    const w = res.data;
                    const content = `
                        <div style="min-width: 220px; font-family: sans-serif;">
                            <div style="border-bottom: 2px solid #0d6efd; padding-bottom: 4px; margin-bottom: 8px;">
                                <span style="background-color: #0d6efd; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.725rem; font-weight: bold; float: right;">
                                    Map Click Lookup
                                </span>
                                <h6 style="margin: 0; font-weight: bold; color: #212529;">${escapeHtml(w.city)}</h6>
                                <small style="color: #6c757d;">(${w.latitude}, ${w.longitude})</small>
                            </div>
                            <div style="font-size: 0.85rem; color: #212529;">
                                <div style="margin-bottom: 4px;"><strong>Temperature:</strong> <span style="color: #0d6efd; font-weight: bold;">${w.temperature !== null ? w.temperature.toFixed(1) + '°C' : '--'}</span></div>
                                <div style="margin-bottom: 4px;"><strong>Condition:</strong> ${escapeHtml(w.weather_condition)} (${escapeHtml(w.weather_description)})</div>
                                <div style="margin-bottom: 4px;"><strong>Humidity:</strong> ${w.humidity}%</div>
                                <div style="margin-bottom: 4px;"><strong>Wind Speed:</strong> ${w.wind_speed} m/s</div>
                                <div style="margin-top: 6px; font-size: 0.725rem; color: #6c757d;">
                                    <i class="bi bi-clock"></i> Recorded: ${escapeHtml(w.recorded_at)}
                                </div>
                            </div>
                        </div>
                    `;
                    tempClickMarker.setPopupContent(content);
                } else {
                    tempClickMarker.setPopupContent(`
                        <div style="min-width: 180px; text-align: center; color: #dc3545; font-size: 0.85rem;">
                            <i class="bi bi-exclamation-triangle-fill me-1"></i> ${escapeHtml(res.error || "Unable to fetch location weather.")}
                        </div>
                    `);
                }
            })
            .catch(err => {
                tempClickMarker.setPopupContent(`
                    <div style="min-width: 180px; text-align: center; color: #dc3545; font-size: 0.85rem;">
                        <i class="bi bi-exclamation-triangle-fill me-1"></i> Network error fetching weather.
                    </div>
                `);
            });
    });

    // Initial data fetch
    fetchAndRenderMapData();
});
