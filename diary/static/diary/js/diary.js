// diary.js

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(cookie => {
            const [key, value] = cookie.trim().split('=');
            if (key === name) cookieValue = decodeURIComponent(value);
        });
    }
    return cookieValue;
}

function colorHint(diff) {
    if (Math.abs(diff) < 1) return "green";
    if (Math.abs(diff) <= 2) return "yellow";
    return "red";
}

function updatePredictions(data) {
    Object.entries(data).forEach(([key, obj]) => {
        const predDiv = document.getElementById(`predicted-${key}`);
        const altDiv  = document.getElementById(`predicted-alt-${key}`);
        if (!predDiv) return;

        const val = obj?.value;
        const inputVal = parseFloat(document.getElementById(`input-${key}`)?.value || 0);

        if (typeof val === "number" && !isNaN(val)) {
            const diff = val - inputVal;
            predDiv.textContent = `Прогноз: ${val.toFixed(1)}`;
            predDiv.dataset.color = colorHint(diff);
            if (altDiv) altDiv.textContent = `Δ ${diff.toFixed(1)}`;
        } else {
            predDiv.textContent = "Ошибка прогноза";
            predDiv.dataset.color = "";
            if (altDiv) altDiv.textContent = "";
        }
    });
}

function buildTodayValuesForPost() {
    const inputs = document.querySelectorAll("input[id^='input-']");
    const result = {};
    inputs.forEach(input => {
        const name = input.id.replace("input-", "");
        const value = parseFloat(input.value);
        if (!isNaN(value)) result[name] = value;
    });
    return result;
}

function fetchPredictions() {
    const url = document.getElementById("predict-url")?.value || "/predict/";
    fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(buildTodayValuesForPost())
    })
    .then(response => response.json())
    .then(data => updatePredictions(data))
    .catch(error => console.error("Ошибка при получении прогнозов:", error));
}

document.addEventListener("DOMContentLoaded", () => {
    fetchPredictions();
});

document.addEventListener("click", function(e) {
    if (e.target.matches(".rating-buttons button")) {
        const btn = e.target;
        const group = btn.closest(".rating-buttons");
        const name = group.dataset.name;

        group.querySelectorAll("button").forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");

        const valueToSend = btn.dataset.value;
        document.getElementById(`input-${name}`).value = valueToSend;

        const date = document.getElementById("date-input")?.value || "";
        const updateUrl = document.getElementById("update-url")?.value || "/update-value/";

        fetch(updateUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({ parameter: name, value: valueToSend, date })
        })
        .then(res => res.json())
        .then(() => fetchPredictions())
        .catch(err => console.error("Ошибка при обновлении значения:", err));
    }
});
