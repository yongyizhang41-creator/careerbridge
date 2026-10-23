// Shows a recruiter where a job's applicants are based, grouped into clusters (US19).
(function () {
    "use strict";

    const root = document.getElementById("applicant-map");
    if (!root) {
        return;
    }

    const Maps = window.CareerBridgeMaps;
    const points = JSON.parse(document.getElementById("applicant-points").textContent);
    const office = root.dataset.officeLat
        ? [parseFloat(root.dataset.officeLng), parseFloat(root.dataset.officeLat)]
        : null;

    const map = Maps.createMap(root, { center: office || Maps.ATLANTA, zoom: 9 });
    if (!map) {
        return;
    }
    // Handy for checking the map in the browser console or in tests.
    window.applicantMap = map;

    if (office) {
        new maplibregl.Marker({ element: Maps.pinElement("div", root.dataset.officeLabel), anchor: "bottom" })
            .setLngLat(office)
            .addTo(map);
    }

    // MapLibre groups nearby points into clusters when the source is told to.
    const geojson = {
        type: "FeatureCollection",
        features: points.map(function (point) {
            return {
                type: "Feature",
                properties: point,
                geometry: { type: "Point", coordinates: [point.lng, point.lat] },
            };
        }),
    };

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

    function popupContent(applicant) {
        const box = element("div", "pop");
        box.append(element("p", "pop__title", applicant.name));
        if (applicant.location) {
            box.append(element("p", "pop__line", applicant.location));
        }
        const tags = element("div", "pop__tags");
        tags.append(element("span", "badge", applicant.status));
        box.append(tags);
        const link = element("a", "button button--small", "View application");
        link.href = applicant.url;
        box.append(link);
        return box;
    }

    map.on("load", function () {
        map.addSource("applicants", {
            type: "geojson",
            data: geojson,
            cluster: true,
            clusterMaxZoom: 14,
            clusterRadius: 50,
        });
        // Bigger circles for bigger clusters: 1-4, 5-19, 20+ applicants.
        map.addLayer({
            id: "clusters",
            type: "circle",
            source: "applicants",
            filter: ["has", "point_count"],
            paint: {
                "circle-color": "#0f766e",
                "circle-radius": ["step", ["get", "point_count"], 18, 5, 24, 20, 32],
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 2,
            },
        });
        map.addLayer({
            id: "cluster-count",
            type: "symbol",
            source: "applicants",
            filter: ["has", "point_count"],
            layout: {
                "text-field": ["get", "point_count_abbreviated"],
                "text-font": ["Noto Sans Bold"],
                "text-size": 13,
            },
            paint: { "text-color": "#ffffff" },
        });
        map.addLayer({
            id: "applicant",
            type: "circle",
            source: "applicants",
            filter: ["!", ["has", "point_count"]],
            paint: {
                "circle-color": "#0f766e",
                "circle-radius": 8,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 2,
            },
        });

        if (points.length) {
            const bounds = new maplibregl.LngLatBounds();
            points.forEach(function (point) {
                bounds.extend([point.lng, point.lat]);
            });
            if (office) {
                bounds.extend(office);
            }
            map.fitBounds(bounds, { padding: 60, maxZoom: 12, duration: 0 });
        }

        // Clicking a cluster zooms in far enough to split it apart.
        map.on("click", "clusters", async function (event) {
            const cluster = event.features[0];
            const zoom = await map.getSource("applicants").getClusterExpansionZoom(cluster.properties.cluster_id);
            map.easeTo({ center: cluster.geometry.coordinates, zoom: zoom });
        });

        map.on("click", "applicant", function (event) {
            const feature = event.features[0];
            new maplibregl.Popup({ offset: 12, maxWidth: "18rem" })
                .setLngLat(feature.geometry.coordinates)
                .setDOMContent(popupContent(feature.properties))
                .addTo(map);
        });

        ["clusters", "applicant"].forEach(function (layer) {
            map.on("mouseenter", layer, function () {
                map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", layer, function () {
                map.getCanvas().style.cursor = "";
            });
        });
    });
})();
