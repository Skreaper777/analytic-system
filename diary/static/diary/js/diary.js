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
            if (altDiv) {
                altDiv.textContent = `Δ ${diff > 0 ? "+" : ""}${diff.toFixed(1)}`;
            }
        } else {
            predDiv.textContent = "Ошибка прогноза";
            predDiv.dataset.color = "red";
            if (altDiv) {
                altDiv.textContent = "";
            }
        }
    });
}

function fetchPredictions(formValues, predictUrl) {
    fetch(predictUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie('csrftoken')
        },
        body: JSON.stringify(formValues)
    })
    .then(resp => resp.json())
    .then(updatePredictions)
    .catch(err => console.warn("Prediction error:", err));
}

document.addEventListener("DOMContentLoaded", function () {
    const formValues = {};
    const allKeys = JSON.parse(document.getElementById("param-keys").textContent);
    const predictUrl = document.getElementById("predict-url").value;
    const updateUrl  = document.getElementById("update-url").value;

    allKeys.forEach(name => {
        const input = document.getElementById(`input-${name}`);
        if (input && input.value !== "") {
            formValues[name] = input.value;
        }
    });

    document.querySelectorAll('.rating-buttons').forEach(group => {
        const name = group.dataset.name;
        const hiddenInput = document.getElementById(`input-${name}`);
        const buttons = group.querySelectorAll('button');

        buttons.forEach(btn => {
            if (hiddenInput.value && parseFloat(btn.dataset.value) === parseFloat(hiddenInput.value)) {
                btn.classList.add('selected');
            }
        });

        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const isActive = btn.classList.contains('selected');
                let valueToSend;

                if (isActive) {
                    hiddenInput.value = '';
                    delete formValues[name];
                    buttons.forEach(b => b.classList.remove('selected'));
                    valueToSend = null;
                } else {
                    const val = btn.dataset.value;
                    hiddenInput.value = val;
                    formValues[name] = val;
                    buttons.forEach(b => b.classList.remove('selected'));
                    btn.classList.add('selected');
                    valueToSend = parseFloat(val);
                }

                fetchPredictions(formValues, predictUrl);

                const dateValue = document.getElementById("date-input")?.value || "";
                console.log("📤 Отправка update:", { parameter: name, value: valueToSend, date: dateValue });

                fetch(updateUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie('csrftoken')
                    },
                    body: JSON.stringify({ parameter: name, value: valueToSend, date: dateValue })
                });
            });
        });
    });

    fetchPredictions(formValues, predictUrl);
});