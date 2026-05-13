document.addEventListener("DOMContentLoaded", function () {
    var DRAFT_KEY = "gaaf_draft_" + window.location.pathname;

    // ── Char counters ─────────────────────────────────────────────────────────
    document.querySelectorAll("textarea[data-max]").forEach(function (ta) {
        var max = parseInt(ta.dataset.max);
        var counter = document.createElement("small");
        counter.className = "char-counter text-muted d-block text-end";
        ta.parentNode.appendChild(counter);
        function update() {
            var len = ta.value.length;
            counter.textContent = len + " / " + max;
            counter.classList.remove("aviso", "limite");
            if (len >= max) counter.classList.add("limite");
            else if (len > max * 0.85) counter.classList.add("aviso");
        }
        ta.addEventListener("input", update);
        update();
    });

    // ── Auto-save draft (only for new record form) ────────────────────────────
    var form = document.getElementById("formOcorrencia");
    if (form && !form.dataset.edicao) {
        var saved = localStorage.getItem(DRAFT_KEY);
        if (saved) {
            try {
                var data = JSON.parse(saved);
                Object.keys(data).forEach(function (name) {
                    var el = form.querySelector('[name="' + name + '"]');
                    if (el && !el.value) el.value = data[name];
                });
                if (typeof gaafToast === "function") gaafToast("Rascunho anterior restaurado.", "info");
            } catch (e) {}
        }
        var draftTimer;
        form.addEventListener("input", function () {
            clearTimeout(draftTimer);
            draftTimer = setTimeout(function () {
                var obj = {};
                new FormData(form).forEach(function (v, k) { obj[k] = v; });
                localStorage.setItem(DRAFT_KEY, JSON.stringify(obj));
            }, 1200);
        });
        form.addEventListener("submit", function () {
            localStorage.removeItem(DRAFT_KEY);
        });
    }

    // ── Quick date / time fill ────────────────────────────────────────────────
    var btnHoje = document.getElementById("btnHoje");
    var btnAgora = document.getElementById("btnAgora");
    if (btnHoje) {
        btnHoje.addEventListener("click", function () {
            var d = form ? form.querySelector('[name="data"]') : document.querySelector('[name="data"]');
            if (d) d.value = new Date().toISOString().slice(0, 10);
        });
    }
    if (btnAgora) {
        btnAgora.addEventListener("click", function () {
            var now = new Date();
            var h = form ? form.querySelector('[name="hora"]') : document.querySelector('[name="hora"]');
            if (h) h.value = now.toTimeString().slice(0, 5);
        });
    }

    // ── Clear form ────────────────────────────────────────────────────────────
    var btnLimpar = document.getElementById("btnLimparForm");
    if (btnLimpar && form) {
        btnLimpar.addEventListener("click", function () {
            if (confirm("Limpar todos os campos do formulário?")) {
                form.reset();
                localStorage.removeItem(DRAFT_KEY);
            }
        });
    }

    // ── Password strength ─────────────────────────────────────────────────────
    var passInput = document.getElementById("inputPassword");
    var strengthBar = document.getElementById("strengthBar");
    var strengthLabel = document.getElementById("strengthLabel");
    if (passInput && strengthBar) {
        passInput.addEventListener("input", function () {
            var v = this.value;
            var score = 0;
            if (v.length >= 6) score++;
            if (v.length >= 10) score++;
            if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
            if (/\d/.test(v)) score++;
            if (/[^A-Za-z0-9]/.test(v)) score++;
            var labels = ["", "Fraca", "Fraca", "Média", "Boa", "Forte"];
            var classes = ["", "strength-fraca", "strength-fraca", "strength-media", "strength-boa", "strength-forte"];
            strengthBar.className = "strength-bar " + (classes[score] || "");
            strengthBar.style.width = (score * 20) + "%";
            if (strengthLabel) strengthLabel.textContent = labels[score] || "";
        });
    }

    // ── Password match indicator ──────────────────────────────────────────────
    var pass2 = document.getElementById("inputPassword2");
    if (passInput && pass2) {
        function checkMatch() {
            var match = passInput.value.length > 0 && passInput.value === pass2.value;
            var typed = pass2.value.length > 0;
            pass2.classList.toggle("is-valid", match);
            pass2.classList.toggle("is-invalid", typed && !match);
        }
        pass2.addEventListener("input", checkMatch);
        passInput.addEventListener("input", checkMatch);
    }

    // ── Login: Enter key navigates fields ─────────────────────────────────────
    var emailField = document.getElementById("loginEmail");
    var passField = document.getElementById("loginPass");
    if (emailField && passField) {
        emailField.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); passField.focus(); }
        });
    }
});
