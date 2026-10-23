// Shared map helpers used by the job form, job detail, and job map pages.
(function () {
    "use strict";

    const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
    const ATLANTA = [-84.3963, 33.7756];
    const PIN_SVG =
        '<svg viewBox="0 0 30 38" aria-hidden="true" focusable="false">' +
        '<path class="pin__body" d="M15 1.5C7.8 1.5 2 7.2 2 14.3 2 24 15 36.5 15 36.5S28 24 28 14.3C28 7.2 22.2 1.5 15 1.5z"/>' +
        '<circle class="pin__dot" cx="15" cy="14.3" r="5"/></svg>';

    function showFallback(container) {
        container.replaceChildren();
        const message = document.createElement("p");
        message.className = "map__fallback";
        message.textContent = "The map couldn't load. Check your connection and refresh the page.";
        container.append(message);
    }

    // Returns a MapLibre map, or null when the map library or WebGL is unavailable.
    function createMap(container, options) {
        const opts = options || {};
        if (!window.maplibregl) {
            showFallback(container);
            return null;
        }
        let map;
        try {
            map = new maplibregl.Map({
                container: container,
                style: STYLE_URL,
                center: opts.center || ATLANTA,
                zoom: opts.zoom === undefined ? 11 : opts.zoom,
                attributionControl: { compact: true },
                dragRotate: false,
                pitchWithRotate: false,
            });
        } catch (error) {
            showFallback(container);
            return null;
        }
        map.touchZoomRotate.disableRotation();
        map.keyboard.disableRotation();
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        if (opts.scrollZoom === false) {
            map.scrollZoom.disable();
        }
        return map;
    }

    function pinElement(tagName, label) {
        const pin = document.createElement(tagName);
        pin.className = "pin";
        if (tagName === "button") {
            pin.type = "button";
        }
        if (label) {
            pin.setAttribute("aria-label", label);
        }
        pin.innerHTML = PIN_SVG;
        return pin;
    }

    // Read-only maps with a single pin, e.g. the office location on a job page.
    function renderPinMap(container) {
        const lngLat = [parseFloat(container.dataset.lng), parseFloat(container.dataset.lat)];
        const map = createMap(container, { center: lngLat, zoom: 15, scrollZoom: false });
        if (!map) {
            return;
        }
        new maplibregl.Marker({ element: pinElement("div", container.dataset.label), anchor: "bottom" })
            .setLngLat(lngLat)
            .addTo(map);
    }

    window.CareerBridgeMaps = { STYLE_URL, ATLANTA, createMap, pinElement };

    // Deferred scripts run after the document is parsed, so the elements already exist.
    document.querySelectorAll("[data-pin-map]").forEach(renderPinMap);
})();
