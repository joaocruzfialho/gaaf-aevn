// Renderiza os gráficos da página de estatísticas com base no JSON embutido.
(function () {
    function corPara(i, total) {
        const hue = Math.round((360 * i) / Math.max(total, 1));
        return `hsl(${hue}, 65%, 55%)`;
    }

    function tema() {
        return document.documentElement.getAttribute("data-bs-theme") === "dark"
            ? { txt: "#e6e6e6", grid: "rgba(255,255,255,0.1)" }
            : { txt: "#222",    grid: "rgba(0,0,0,0.08)" };
    }

    document.addEventListener("DOMContentLoaded", function () {
        const raw = document.getElementById("dadosStats");
        if (!raw) return;
        const stats = JSON.parse(raw.textContent);
        const t = tema();
        Chart.defaults.color = t.txt;
        Chart.defaults.borderColor = t.grid;

        document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
            const chave = canvas.dataset.chart;
            const tipo = canvas.dataset.tipo || "bar";
            const horizontal = canvas.dataset.horizontal === "1";
            const dados = stats[chave] || [];
            if (!dados.length) {
                canvas.parentElement.insertAdjacentHTML(
                    "beforeend",
                    '<div class="text-muted small text-center py-3">Sem dados no período.</div>'
                );
                canvas.remove();
                return;
            }
            const labels = dados.map(d => d[0]);
            const valores = dados.map(d => d[1]);
            const cores = dados.map((_, i) => corPara(i, dados.length));

            const config = {
                type: tipo,
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Ocorrências",
                        data: valores,
                        backgroundColor: cores,
                        borderColor: cores,
                        borderWidth: 1,
                        tension: 0.3,
                        fill: tipo === "line" ? false : true,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: horizontal ? "y" : "x",
                    plugins: {
                        legend: { display: tipo === "doughnut" || tipo === "pie" },
                    },
                    scales: (tipo === "doughnut" || tipo === "pie") ? {} : {
                        x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 0 } },
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                },
            };
            new Chart(canvas, config);
        });
    });
})();
