const form = document.getElementById('analyzer-form');
const resultsPanel = document.getElementById('results-panel');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const title = document.getElementById('job-title').value;
    const desc = document.getElementById('job-desc').value;

    if (!desc) {
        alert("Description required");
        return;
    }

    // Show loading
    resultsPanel.classList.remove('hidden');
    document.getElementById('result-title').innerText = "Analyzing...";
    document.getElementById('result-message').innerText = "AI is thinking...";
    document.getElementById('score-text').innerText = "0%";

    try {
        const res = await fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description: desc })
        });

        const data = await res.json();

        // ===== FINAL RESULT =====
        document.getElementById('result-title').innerText = data.prediction;
        document.getElementById('result-message').innerText = data.message;

        document.getElementById('score-text').innerText = data.confidence + "%";

        // Circle animation
        const circle = document.getElementById('score-path');
        circle.setAttribute("stroke-dasharray", `${data.confidence}, 100`);

        // Badge
        const badge = document.getElementById('threat-badge');
        badge.innerText = data.prediction;
        badge.style.background = data.is_fraudulent ? "#dc2626" : "#16a34a";

        // ===== MODEL DETAILS =====
        document.getElementById('svm').innerText =
            data.all_models["SVM"].label + " (" +
            data.all_models["SVM"].confidence + "%)";

        document.getElementById('rf').innerText =
            data.all_models["Random Forest"].label + " (" +
            data.all_models["Random Forest"].confidence + "%)";

        document.getElementById('nb').innerText =
            data.all_models["Naive Bayes"].label + " (" +
            data.all_models["Naive Bayes"].confidence + "%)";

        document.getElementById('final').innerText =
            `${data.prediction} (${data.confidence}% confidence using ${data.model_used})`;

        loadHistory();

    } catch (err) {
        alert("Something went wrong");
        console.error(err);
    }
});

// RESET BUTTON
document.getElementById('reset-btn').addEventListener('click', () => {
    form.reset();
    resultsPanel.classList.add('hidden');
});

// ===== HISTORY =====
async function loadHistory() {
    try {
        const res = await fetch('/history');
        const data = await res.json();

        let html = '';

        data.forEach(job => {
            html += `
            <tr>
                <td>${job.title}</td>
                <td>${job.prediction_label}</td>
                <td>${job.probability}%</td>
                <td>${job.model_used}</td>
            </tr>`;
        });

        document.getElementById('history-body').innerHTML = html;

    } catch (err) {
        console.error("History load failed", err);
    }
}

// Initial load
loadHistory();