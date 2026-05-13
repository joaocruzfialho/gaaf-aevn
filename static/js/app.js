// Apply saved theme immediately (before DOMContentLoaded) to avoid flash
(function () {
    var saved = localStorage.getItem("gaaf_tema");
    if (saved === "dark" || saved === "light") {
        document.documentElement.setAttribute("data-bs-theme", saved);
    }
})();

document.addEventListener("DOMContentLoaded", function () {

    // ── Theme toggle ──────────────────────────────────────────────────────────
    function toggleTheme() {
        var html = document.documentElement;
        var next = (html.getAttribute("data-bs-theme") || "light") === "dark" ? "light" : "dark";
        html.setAttribute("data-bs-theme", next);
        localStorage.setItem("gaaf_tema", next);
    }
    ["toggleTema", "toggleTemaLogin"].forEach(function (id) {
        var btn = document.getElementById(id);
        if (btn) btn.addEventListener("click", toggleTheme);
    });

    // ── Show / hide password ──────────────────────────────────────────────────
    document.querySelectorAll(".btn-mostrar-pass").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var input = document.getElementById(this.dataset.target);
            if (!input) return;
            var showing = input.type === "text";
            input.type = showing ? "password" : "text";
            var icon = this.querySelector("i");
            if (icon) icon.className = showing ? "bi bi-eye" : "bi bi-eye-slash";
        });
    });

    // ── Back-to-top ───────────────────────────────────────────────────────────
    var btnTopo = document.getElementById("btnTopo");
    if (btnTopo) {
        window.addEventListener("scroll", function () {
            btnTopo.classList.toggle("d-none", window.scrollY < 300);
        }, { passive: true });
        btnTopo.addEventListener("click", function () {
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    // ── Mobile navbar: auto-close on nav-link click ───────────────────────────
    var navMenu = document.getElementById("navMenu");
    if (navMenu) {
        navMenu.querySelectorAll(".nav-link").forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.innerWidth < 992) {
                    var bsCollapse = bootstrap.Collapse.getInstance(navMenu);
                    if (bsCollapse) bsCollapse.hide();
                }
            });
        });
    }

    // ── Active nav link ───────────────────────────────────────────────────────
    var path = window.location.pathname;
    document.querySelectorAll(".nav-link, .bottom-nav a").forEach(function (link) {
        var href = link.getAttribute("href");
        if (!href) return;
        if (href === "/" && path === "/") {
            link.classList.add("active");
        } else if (href !== "/" && path.startsWith(href)) {
            link.classList.add("active");
        }
    });

    // ── Keyboard shortcut Alt+N → nova ocorrência ────────────────────────────
    document.addEventListener("keydown", function (e) {
        if (e.altKey && e.key.toLowerCase() === "n") {
            var link = document.querySelector('a[href*="nova-ocorrencia"]');
            if (link) { e.preventDefault(); link.click(); }
        }
    });

    // ── Clipboard copy buttons ────────────────────────────────────────────────
    document.querySelectorAll(".btn-copiar").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var text = this.dataset.texto;
            if (!text) {
                var el = document.getElementById(this.dataset.id);
                if (el) text = el.innerText;
            }
            if (!text) return;
            navigator.clipboard.writeText(text).then(function () {
                gaafToast("Copiado para a área de transferência.", "success");
            });
        });
    });

    // ── Table sort (th.sortable) ──────────────────────────────────────────────
    document.querySelectorAll("table.sortable-table").forEach(function (table) {
        var ths = table.querySelectorAll("thead th.sortable");
        ths.forEach(function (th) {
            th.style.cursor = "pointer";
            th.title = "Clique para ordenar";
            th.addEventListener("click", function () {
                var colIdx = Array.from(th.parentNode.children).indexOf(th);
                var asc = !th.classList.contains("sort-asc");
                ths.forEach(function (h) { h.classList.remove("sort-asc", "sort-desc"); });
                th.classList.add(asc ? "sort-asc" : "sort-desc");
                var tbody = table.querySelector("tbody");
                var rows = Array.from(tbody.querySelectorAll("tr"));
                rows.sort(function (a, b) {
                    var va = (a.cells[colIdx] ? a.cells[colIdx].innerText.trim() : "");
                    var vb = (b.cells[colIdx] ? b.cells[colIdx].innerText.trim() : "");
                    return asc ? va.localeCompare(vb, "pt") : vb.localeCompare(va, "pt");
                });
                rows.forEach(function (r) { tbody.appendChild(r); });
            });
        });
    });

    // ── Real-time search ──────────────────────────────────────────────────────
    var searchInput = document.getElementById("pesquisaRapida");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            var q = this.value.toLowerCase().trim();
            document.querySelectorAll("table.sortable-table tbody tr").forEach(function (tr) {
                tr.style.display = !q || tr.innerText.toLowerCase().includes(q) ? "" : "none";
            });
            document.querySelectorAll(".card-ocorrencia-mobile").forEach(function (card) {
                card.style.display = !q || card.innerText.toLowerCase().includes(q) ? "" : "none";
            });
        });
    }

    // ── Per-page selector ─────────────────────────────────────────────────────
    var perPageSelect = document.getElementById("porPagina");
    if (perPageSelect) {
        perPageSelect.addEventListener("change", function () {
            var n = parseInt(this.value);
            var rows = document.querySelectorAll("table.sortable-table tbody tr");
            rows.forEach(function (tr, i) {
                tr.style.display = (n === 0 || i < n) ? "" : "none";
            });
            var cards = document.querySelectorAll(".card-ocorrencia-mobile");
            cards.forEach(function (card, i) {
                card.style.display = (n === 0 || i < n) ? "" : "none";
            });
        });
    }

});

// ── Global toast function ─────────────────────────────────────────────────────
function gaafToast(mensagem, tipo) {
    tipo = tipo || "info";
    var container = document.getElementById("toastContainer");
    if (!container) return;
    var div = document.createElement("div");
    div.className = "toast gaaf-toast toast-" + tipo + " align-items-center border-0";
    div.setAttribute("role", "alert");
    div.setAttribute("aria-live", "assertive");
    div.setAttribute("aria-atomic", "true");
    div.innerHTML = '<div class="d-flex"><div class="toast-body">' + mensagem + '</div>'
        + '<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button></div>';
    container.appendChild(div);
    var toast = new bootstrap.Toast(div, { delay: 4000 });
    toast.show();
    div.addEventListener("hidden.bs.toast", function () { div.remove(); });
}
