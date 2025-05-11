
document.addEventListener("DOMContentLoaded", function () {
    const diary = document.getElementById("diary");
    const predictUrl = diary.dataset.urlPredict;
    const updateUrl = diary.dataset.urlUpdate;
    const entryDate = diary.dataset.today;
    const paramKeys = JSON.parse(document.getElementById("param-keys").textContent);

    const formValues = {};

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            document.cookie.split(";").forEach(cookie => {
                const [key, value] = cookie.trim().split("=");
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
        const altDiv = document.getElementById(`predicted-alt-${key}`);
        if (!predDiv) return;
        const inputVal = parseFloat(document.getElementById(`input-${key}`).value) || 0;

        if (typeof val === "number" && !isNaN(val)) {
            const diff = val - inputVal;
            predDiv.textContent = `Прогноз: ${val.toFixed(1)}`;
            predDiv.dataset.color = colorHint(diff);
            if (altDiv) altDiv.textContent = `Δ ${diff > 0 ? "+" : ""}${diff.toFixed(1)}`;
        } else {
            predDiv.textContent = "Ошибка прогноза";
            predDiv.dataset.color = "red";
            if (altDiv) altDiv.textContent = "";
        }
    });
}


            predDiv.dataset.color = colorHint(diff);
            if (altDiv) altDiv.textContent = `Δ ${diff > 0 ? "+" : ""}${diff.toFixed(1)}`;
        });
    }

    function fetchPredictions() {
        fetch(predictUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify(formValues)
        })
        .then(resp => resp.json())
        .then(updatePredictions)
        .catch(err => console.warn("Prediction error:", err));
    }

    document.querySelectorAll(".rating-buttons").forEach(group => {
        const name = group.dataset.name;
        const hiddenInput = document.getElementById(`input-${name}`);
        const buttons = group.querySelectorAll("button");

        buttons.forEach(btn => {
            if (hiddenInput.value && parseFloat(btn.dataset.value) === parseFloat(hiddenInput.value)) {
                btn.classList.add("selected");
            }
        });

        buttons.forEach(btn => {
            btn.addEventListener("click", () => {
                const isActive = btn.classList.contains("selected");
                let valueToSend;

                if (isActive) {
                    hiddenInput.value = "";
                    delete formValues[name];
                    buttons.forEach(b => b.classList.remove("selected"));
                    valueToSend = null;
                } else {
                    const val = btn.dataset.value;
                    hiddenInput.value = val;
                    formValues[name] = val;
                    buttons.forEach(b => b.classList.remove("selected"));
                    btn.classList.add("selected");
                    valueToSend = parseFloat(val);
                }

                fetchPredictions();
                fetch(updateUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken")
                    },
                    body: JSON.stringify({
                        key: name,
                        value: valueToSend,
                        date: entryDate
                    })
                });
            });
        });
    });

    fetchPredictions();
});
