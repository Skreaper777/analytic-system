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
    Object.entries(data).forEach(([key, val]) => {
        const predDiv = document.getElementById(`predicted-${key}`);
        const altDiv  = document.getElementById(`predicted-alt-${key}`);
        if (!predDiv) return;
        const inputVal = parseFloat(document.getElementById(`input-${key}`).value) || 0;

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

function fetchPredictions() {
    fetch("/predict/")
        .then(response => response.json())
        .then(data => updatePredictions(data))
        .catch(error => console.error("Ошибка при получении прогнозов:", error));
}

document.addEventListener("DOMContentLoaded", () => {
    fetchPredictions();  // 🚀 начальная загрузка прогнозов
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

        fetch("/update-value/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                parameter: name,
                value: valueToSend,
                date: document.getElementById("date-input")?.value || ""
            })
        }).then(data => {
            fetchPredictions();  // 🔁 автообновление базового прогноза
        });
    }
});