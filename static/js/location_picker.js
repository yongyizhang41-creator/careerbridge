// Lets a recruiter pin the job's office location on the job form (US18),
// and a job seeker pin their own location on the profile form (US19).
(function () {
    "use strict";

    const root = document.getElementById("location-picker");
    if (!root) {
        return;
    }

    const Maps = window.CareerBridgeMaps;
    const card = root.closest(".location-card");
    const latInput = document.getElementById(root.dataset.latInput);
    const lngInput = document.getElementById(root.dataset.lngInput);
    const addressInput = document.getElementById(root.dataset.addressInput);
    const badge = card.querySelector("[data-pin-badge]");
    const coords = card.querySelector("[data-pin-coords]");
    const message = card.querySelector("[data-pin-message]");
    const findButton = card.querySelector("[data-find-address]");
    const clearButton = card.querySelector("[data-clear-pin]");

    function readInputs() {
        const lat = parseFloat(latInput.value);
        const lng = parseFloat(lngInput.value);
        return Number.isFinite(lat) && Number.isFinite(lng) ? { lat: lat, lng: lng } : null;
    }

    function showMessage(text, isError) {
        message.textContent = text || "";
        message.hidden = !text;
        message.classList.toggle("is-error", Boolean(isError));
    }

    function render() {
        const pin = readInputs();
        badge.textContent = pin ? "Pinned" : "No pin yet";
        badge.classList.toggle("badge--muted", !pin);
        coords.textContent = pin ? pin.lat.toFixed(5) + ", " + pin.lng.toFixed(5) : "Not pinned yet";
        clearButton.disabled = !pin;
    }

    const initial = readInputs();
    const map = Maps.createMap(root, {
        center: initial ? [initial.lng, initial.lat] : Maps.ATLANTA,
        zoom: initial ? 15 : 11,
    });
    render();
    if (!map) {
        findButton.disabled = true;
        return;
    }

    let marker = null;

    function setPin(lngLat, note) {
        // Clicks on a wrapped copy of the world can report longitudes past +/-180.
        const point = new maplibregl.LngLat(lngLat.lng, lngLat.lat).wrap();
        latInput.value = point.lat.toFixed(6);
        lngInput.value = point.lng.toFixed(6);
        if (!marker) {
            const pin = Maps.pinElement("div", root.dataset.pinLabel || "Location pin");
            pin.classList.add("pin--draggable");
            marker = new maplibregl.Marker({ element: pin, anchor: "bottom", draggable: true })
                .setLngLat(point)
                .addTo(map);
            marker.on("dragend", function () {
                setPin(marker.getLngLat(), "Pin moved.");
            });
        }
        marker.setLngLat(point);
        render();
        showMessage(note);
    }

    function clearPin() {
        latInput.value = "";
        lngInput.value = "";
        if (marker) {
            marker.remove();
            marker = null;
        }
        render();
        showMessage("Pin cleared.");
    }

    async function findAddress() {
        const query = addressInput.value.trim();
        if (!query) {
            showMessage("Enter the address first, or click the map to place the pin.", true);
            addressInput.focus();
            return;
        }
        findButton.disabled = true;
        showMessage("Looking up the address...");
        try {
            const params = new URLSearchParams({ q: query, format: "jsonv2", limit: "1" });
            const response = await fetch("https://nominatim.openstreetmap.org/search?" + params);
            if (!response.ok) {
                throw new Error("Lookup failed with status " + response.status);
            }
            const results = await response.json();
            if (!results.length) {
                showMessage("We couldn't find that address. Click the map to place the pin yourself.", true);
                return;
            }
            const lngLat = { lng: parseFloat(results[0].lon), lat: parseFloat(results[0].lat) };
            setPin(lngLat, "Placed from the address. Drag the pin if the entrance is elsewhere.");
            map.flyTo({ center: [lngLat.lng, lngLat.lat], zoom: 16 });
        } catch (error) {
            showMessage("Address lookup isn't available right now. Click the map to place the pin yourself.", true);
        } finally {
            findButton.disabled = false;
        }
    }

    if (initial) {
        setPin(initial, "");
    }
    map.on("click", function (event) {
        setPin(event.lngLat, "Pinned where you clicked. Drag the pin to adjust.");
    });
    findButton.addEventListener("click", findAddress);
    clearButton.addEventListener("click", clearPin);
})();
