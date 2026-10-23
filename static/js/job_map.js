// Lets job seekers browse pinned jobs on a map and locate them from the list (US7),
// hide jobs farther than a chosen distance from where they are (US8),
// and start from their saved commute radius (US9).
(function () {
    "use strict";

    const root = document.getElementById("job-map");
    if (!root) {
        return;
    }

    const Maps = window.CareerBridgeMaps;
    const jobs = JSON.parse(document.getElementById("job-markers").textContent);
    const list = document.querySelector("[data-job-list]");
    const locateButton = document.querySelector("[data-locate]");
    const locateMessage = document.querySelector("[data-locate-message]");
    const radiusSelect = document.querySelector("[data-radius]");
    const radiusEmpty = document.querySelector("[data-radius-empty]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const map = Maps.createMap(root, { center: Maps.ATLANTA, zoom: 11 });
    if (!map) {
        locateButton.disabled = true;
        radiusSelect.disabled = true;
        return;
    }

    const markers = new Map();
    let openPopup = null;
    let youMarker = null;
    let here = null;

    function element(tagName, className, text) {
        const node = document.createElement(tagName);
        if (className) {
            node.className = className;
        }
        if (text) {
            node.textContent = text;
        }
        return node;
    }

    function money(value) {
        return "$" + Number(value).toLocaleString("en-US");
    }

    function salaryText(job) {
        if (job.salary_min && job.salary_max) {
            return money(job.salary_min) + " - " + money(job.salary_max);
        }
        if (job.salary_min) {
            return "From " + money(job.salary_min);
        }
        return job.salary_max ? "Up to " + money(job.salary_max) : "";
    }

    function popupContent(job) {
        const box = element("div", "pop");
        box.append(element("p", "pop__title", job.title));
        box.append(element("p", "pop__line", job.company));
        if (job.address) {
            box.append(element("p", "pop__line", job.address));
        }
        const tags = element("div", "pop__tags");
        tags.append(element("span", "badge", job.remote_type));
        if (job.visa_sponsorship) {
            tags.append(element("span", "badge badge--accent", "Visa sponsorship"));
        }
        box.append(tags);
        if (salaryText(job)) {
            box.append(element("p", "pop__line", salaryText(job)));
        }
        const link = element("a", "button button--small", "View job");
        link.href = job.url;
        box.append(link);
        return box;
    }

    function setActive(jobId) {
        markers.forEach(function (marker, id) {
            marker.getElement().classList.toggle("is-active", id === jobId);
        });
        list.querySelectorAll("[data-job-id]").forEach(function (item) {
            item.classList.toggle("is-active", Number(item.dataset.jobId) === jobId);
        });
    }

    jobs.forEach(function (job) {
        const popup = new maplibregl.Popup({ offset: [0, -36], maxWidth: "18rem" })
            .setDOMContent(popupContent(job));
        popup.on("open", function () {
            if (openPopup && openPopup !== popup) {
                openPopup.remove();
            }
            openPopup = popup;
            setActive(job.id);
        });
        popup.on("close", function () {
            if (openPopup === popup) {
                openPopup = null;
                setActive(null);
            }
        });
        const pin = Maps.pinElement("button", job.title + " at " + job.company);
        const marker = new maplibregl.Marker({ element: pin, anchor: "bottom" })
            .setLngLat([job.lng, job.lat])
            .setPopup(popup)
            .addTo(map);
        markers.set(job.id, marker);
    });

    list.addEventListener("click", function (event) {
        const item = event.target.closest("[data-job-id]");
        const marker = item && markers.get(Number(item.dataset.jobId));
        if (!marker) {
            return;
        }
        map.flyTo({
            center: marker.getLngLat(),
            zoom: Math.max(map.getZoom(), 14),
            duration: reduceMotion ? 0 : 900,
        });
        if (!marker.getPopup().isOpen()) {
            marker.togglePopup();
        }
    });

    function showMessage(text, isError) {
        locateMessage.textContent = text;
        locateMessage.hidden = !text;
        locateMessage.classList.toggle("is-error", Boolean(isError));
    }

    function milesBetween(a, b) {
        const toRad = Math.PI / 180;
        const dLat = (b.lat - a.lat) * toRad;
        const dLng = (b.lng - a.lng) * toRad;
        const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(a.lat * toRad) * Math.cos(b.lat * toRad) * Math.sin(dLng / 2) ** 2;
        return 2 * 3958.8 * Math.asin(Math.sqrt(h));
    }

    // Label each listed job with its distance and list the nearest first.
    function showDistances(here) {
        const rows = Array.from(list.querySelectorAll("[data-job-id]")).map(function (item) {
            const lngLat = markers.get(Number(item.dataset.jobId)).getLngLat();
            const miles = milesBetween(here, { lat: lngLat.lat, lng: lngLat.lng });
            let label = item.querySelector(".job-item__distance");
            if (!label) {
                label = element("span", "job-item__distance");
                item.querySelector(".job-item__row").append(label);
            }
            label.textContent = miles.toFixed(1) + " mi away";
            return { li: item.closest("li"), miles: miles };
        });
        rows.sort(function (a, b) { return a.miles - b.miles; });
        rows.forEach(function (row) { list.append(row.li); });
    }

    // The chosen distance in miles, or 0 when "Any distance" is selected.
    function chosenRadius() {
        return Number(radiusSelect.value);
    }

    // A circle of the chosen radius around the job seeker, as GeoJSON for the map.
    // One degree of latitude is about 69 miles; longitude degrees shrink away from the equator.
    function radiusGeoJSON() {
        const miles = chosenRadius();
        const features = [];
        if (here && miles) {
            const latStep = miles / 69;
            const lngStep = miles / (69 * Math.cos(here.lat * Math.PI / 180));
            const ring = [];
            for (let i = 0; i <= 64; i++) {
                const angle = (i / 64) * 2 * Math.PI;
                ring.push([here.lng + lngStep * Math.sin(angle), here.lat + latStep * Math.cos(angle)]);
            }
            features.push({ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] } });
        }
        return { type: "FeatureCollection", features: features };
    }

    map.on("load", function () {
        map.addSource("radius", { type: "geojson", data: radiusGeoJSON() });
        map.addLayer({
            id: "radius-fill",
            type: "fill",
            source: "radius",
            paint: { "fill-color": "#1d6fd8", "fill-opacity": 0.08 },
        });
        map.addLayer({
            id: "radius-line",
            type: "line",
            source: "radius",
            paint: { "line-color": "#1d6fd8", "line-width": 2, "line-dasharray": [2, 2] },
        });
    });

    // Show only the jobs within the chosen distance of the job seeker, and say how many that is.
    function applyRadius() {
        const miles = chosenRadius();
        let shown = 0;
        jobs.forEach(function (job) {
            const marker = markers.get(job.id);
            const item = list.querySelector('[data-job-id="' + job.id + '"]').closest("li");
            const visible = !miles || (here !== null && milesBetween(here, job) <= miles);
            marker.getElement().style.display = visible ? "" : "none";
            item.hidden = !visible;
            if (!visible && marker.getPopup().isOpen()) {
                marker.togglePopup();
            }
            shown += visible ? 1 : 0;
        });
        radiusEmpty.hidden = !(miles && jobs.length && shown === 0);

        const circle = map.getSource("radius");
        if (circle) {
            circle.setData(radiusGeoJSON());
        }

        if (!here) {
            return;
        }
        if (miles) {
            showMessage(shown + " of " + jobs.length + " pinned job" + (jobs.length === 1 ? "" : "s") +
                " within " + miles + " miles of you.");
            fitRadius(miles);
        } else {
            showMessage(jobs.length
                ? "Showing your location. The list is sorted by distance from you."
                : "Showing your location.");
        }
    }

    // Zoom the map so the whole circle is visible.
    function fitRadius(miles) {
        const latStep = miles / 69;
        const lngStep = miles / (69 * Math.cos(here.lat * Math.PI / 180));
        map.fitBounds(
            [[here.lng - lngStep, here.lat - latStep], [here.lng + lngStep, here.lat + latStep]],
            { padding: 40, duration: reduceMotion ? 0 : 900 }
        );
    }

    function onLocation(position) {
        here = { lat: position.coords.latitude, lng: position.coords.longitude };
        if (!youMarker) {
            const dot = element("div", "you");
            dot.setAttribute("role", "img");
            dot.setAttribute("aria-label", "Your location");
            youMarker = new maplibregl.Marker({ element: dot }).setLngLat([here.lng, here.lat]).addTo(map);
        } else {
            youMarker.setLngLat([here.lng, here.lat]);
        }
        map.flyTo({ center: [here.lng, here.lat], zoom: 12, duration: reduceMotion ? 0 : 900 });
        if (jobs.length) {
            showDistances(here);
        }
        applyRadius();
        locateButton.textContent = "Update my location";
        locateButton.disabled = false;
    }

    function onLocationError(error) {
        const blocked = error.code === error.PERMISSION_DENIED;
        showMessage(blocked
            ? "Location access is blocked. Allow it in your browser settings to see jobs near you."
            : "We couldn't get your location. Try again in a moment.", true);
        locateButton.disabled = false;
    }

    function locate() {
        if (!navigator.geolocation) {
            showMessage("This browser can't share your location.", true);
            return;
        }
        locateButton.disabled = true;
        showMessage("Finding your location...");
        navigator.geolocation.getCurrentPosition(onLocation, onLocationError, {
            timeout: 10000,
            maximumAge: 300000,
        });
    }

    locateButton.addEventListener("click", locate);

    // Filtering by distance needs the job seeker's location, so ask for it the first time.
    radiusSelect.addEventListener("change", function () {
        if (chosenRadius() && !here) {
            locate();
        } else {
            applyRadius();
        }
    });

    // A saved commute radius is preselected by the server, so apply it straight away.
    if (chosenRadius()) {
        locate();
    }
})();
