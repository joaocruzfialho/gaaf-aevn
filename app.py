"""Aplicação Flask — Registo de Ocorrências GAAF (Agrupamento de Escolas de Vendas Novas)."""
import os
import csv
import io
import threading
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, Response, jsonify,
)

import database as db


APP_VERSION = "5"
APP_AUTHOR = "Adelina Fialho"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "gaaf-aevn-chave-local-trocar-em-producao")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["ALLOW_SHUTDOWN"] = False  # ativado apenas em modo local (__main__)


# ---------------------------------------------------------------------------
# Filtros Jinja
# ---------------------------------------------------------------------------
@app.template_filter("data_pt")
def _data_pt(s):
    if not s:
        return ""
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return s


@app.template_filter("datahora_pt")
def _datahora_pt(s):
    if not s:
        return ""
    try:
        return datetime.fromisoformat(str(s)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return s


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
with app.app_context():
    db.init_db()


# ---------------------------------------------------------------------------
# Helpers de sessão / autorização
# ---------------------------------------------------------------------------
def utilizador_atual():
    uid = session.get("uid")
    if not uid:
        return None
    return db.obter_utilizador(uid)


def _iniciais(nome):
    partes = (nome or "?").split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[-1][0]).upper()
    return nome[:2].upper() if nome else "?"


@app.context_processor
def inject_globals():
    u = utilizador_atual()
    return {
        "user": u,
        "user_iniciais": _iniciais(u["nome"]) if u else "?",
        "ano_atual": datetime.now().year,
        "app_version": APP_VERSION,
        "app_author": APP_AUTHOR,
        "hoje_str": datetime.now().strftime("%Y-%m-%d"),
    }


def pode_editar_ocorrencia(o, user):
    if not user or not o:
        return False
    if user["perfil"] == "Coordenador":
        return True
    return o.get("criado_por") == user["id"]


def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            flash("Sessão expirada. Por favor faça login.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapper


def coordenador_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        u = utilizador_atual()
        if not u:
            return redirect(url_for("login"))
        if u["perfil"] != "Coordenador":
            flash("Acesso restrito ao Coordenador do GAAF.", "danger")
            return redirect(url_for("home"))
        return view(*a, **kw)
    return wrapper


# ---------------------------------------------------------------------------
# Health check (diagnóstico — remover após confirmar funcionamento)
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    import traceback
    try:
        n = db.contar_coordenadores() + len(db.listar_utilizadores())
        return {"status": "ok", "utilizadores": n // 2, "mode": "supabase" if db.SUPABASE_URL else "sqlite"}
    except Exception as e:
        return {"status": "error", "error": str(e), "trace": traceback.format_exc()}, 500


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("uid"):
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = db.autenticar(email, password)
        if user:
            session["uid"] = user["id"]
            session["nome"] = user["nome"]
            session["perfil"] = user["perfil"]
            if request.form.get("lembrar"):
                session.permanent = True
            flash(f"Bem-vindo(a), {user['nome']}!", "success")
            return redirect(request.args.get("next") or url_for("home"))
        flash("Email ou password incorretos.", "danger")
    return render_template("login.html")


@app.route("/registar", methods=["GET", "POST"])
def registar():
    erro = None
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        perfil = request.form.get("perfil", "Colaborador")
        pergunta = request.form.get("pergunta", "").strip()
        resposta = request.form.get("resposta", "").strip()

        if not (nome and email and password and pergunta and resposta):
            erro = "Preencha todos os campos obrigatórios."
        elif password != password2:
            erro = "As passwords não coincidem."
        elif len(password) < 6:
            erro = "A password deve ter pelo menos 6 caracteres."
        elif perfil not in db.PERFIS:
            erro = "Perfil inválido."
        else:
            ok, msg = db.criar_utilizador(nome, email, password, perfil, pergunta, resposta)
            if ok:
                flash("Conta criada com sucesso. Faça login.", "success")
                return redirect(url_for("login"))
            erro = msg
    return render_template("registar.html", erro=erro)


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    passo = request.form.get("passo", "1")
    contexto = {"passo": passo}
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if passo == "1":
            u = db.obter_utilizador_por_email(email)
            if not u:
                contexto["erro"] = "Não existe conta com esse email."
            else:
                contexto.update({"passo": "2", "email": email,
                                 "pergunta": u["pergunta_seguranca"]})
        elif passo == "2":
            resposta = request.form.get("resposta", "")
            if db.verificar_resposta_seguranca(email, resposta):
                contexto.update({"passo": "3", "email": email})
            else:
                u = db.obter_utilizador_por_email(email)
                contexto.update({
                    "passo": "2", "email": email,
                    "pergunta": u["pergunta_seguranca"] if u else "",
                    "erro": "Resposta incorreta.",
                })
        elif passo == "3":
            nova = request.form.get("password", "")
            nova2 = request.form.get("password2", "")
            if nova != nova2:
                contexto.update({"passo": "3", "email": email,
                                 "erro": "As passwords não coincidem."})
            elif len(nova) < 6:
                contexto.update({"passo": "3", "email": email,
                                 "erro": "Mínimo 6 caracteres."})
            else:
                db.atualizar_password(email, nova)
                flash("Password atualizada. Faça login.", "success")
                return redirect(url_for("login"))
    return render_template("recuperar.html", **contexto)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/encerrar", methods=["POST"])
def encerrar():
    if not app.config.get("ALLOW_SHUTDOWN", False):
        return ("", 204)  # em produção não faz nada
    def _kill():
        import time
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_kill, daemon=True).start()
    return ("", 204)


# ---------------------------------------------------------------------------
# Minha Conta
# ---------------------------------------------------------------------------
@app.route("/minha-conta", methods=["GET", "POST"])
@login_required
def minha_conta():
    u = utilizador_atual()
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "nome":
            novo_nome = request.form.get("nome", "").strip()
            if not novo_nome:
                flash("O nome não pode estar vazio.", "danger")
            else:
                db.atualizar_utilizador(u["id"], novo_nome)
                session["nome"] = novo_nome
                flash("Nome atualizado com sucesso.", "success")
        elif acao == "password":
            atual = request.form.get("atual", "")
            nova = request.form.get("nova", "")
            nova2 = request.form.get("nova2", "")
            if not db.autenticar(u["email"], atual):
                flash("Password atual incorreta.", "danger")
            elif nova != nova2:
                flash("As novas passwords não coincidem.", "danger")
            elif len(nova) < 6:
                flash("A nova password deve ter mínimo 6 caracteres.", "danger")
            else:
                db.atualizar_password(u["email"], nova)
                flash("Password alterada com sucesso.", "success")
        return redirect(url_for("minha_conta"))
    return render_template("minha_conta.html")


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
@app.route("/home")
@login_required
def home():
    stats = db.estatisticas(periodo="ano")
    return render_template("home.html", stats=stats,
                           hoje=db.contar_hoje(),
                           semana=db.contar_semana(),
                           mes=db.contar_mes(),
                           recentes=db.listar_ocorrencias_recentes(5))


# ---------------------------------------------------------------------------
# Ocorrências
# ---------------------------------------------------------------------------
def _form_para_dados():
    return {c: request.form.get(c, "").strip() for c in db.CAMPOS_OCORRENCIA}


def _opcoes():
    return {
        "ciclos": db.CICLOS, "anos": db.ANOS, "locais": db.LOCAIS,
        "com_quem": db.COM_QUEM, "destruicao": db.DESTRUICAO,
        "contactos_ee": db.CONTACTOS_EE, "motivos": db.MOTIVOS,
        "situacoes": db.SITUACOES, "disciplinas": db.DISCIPLINAS,
        "nomes_alunos": db.listar_nomes_alunos(),
    }


@app.route("/ocorrencias/nova", methods=["GET", "POST"])
@login_required
def nova_ocorrencia():
    u = utilizador_atual()
    if request.method == "POST":
        dados = _form_para_dados()
        if not dados.get("data"):
            flash("A data é obrigatória.", "danger")
            return render_template("ocorrencia_form.html", dados=dados,
                                   numero=db.proximo_numero(), **_opcoes())
        if not dados.get("colaborador"):
            dados["colaborador"] = u["nome"]
        novo = db.criar_ocorrencia(dados, u["id"])
        flash(f"Ocorrência nº {novo:03d} registada com sucesso.", "success")
        return redirect(url_for("listar_ocorrencias"))

    dados = {c: "" for c in db.CAMPOS_OCORRENCIA}
    dados["data"] = datetime.now().strftime("%Y-%m-%d")
    dados["hora"] = datetime.now().strftime("%H:%M")
    dados["colaborador"] = u["nome"]
    dados["situacao"] = "Em análise"
    return render_template("ocorrencia_form.html", dados=dados,
                           numero=db.proximo_numero(), **_opcoes())


@app.route("/ocorrencias")
@login_required
def listar_ocorrencias():
    filtros = {k: request.args.get(k, "").strip() for k in
               ("ciclo", "ano", "turma", "disciplina", "local", "motivo",
                "data_de", "data_ate", "texto", "situacao")}
    ocorrencias = db.listar_ocorrencias(filtros)
    if filtros.get("situacao"):
        ocorrencias = [o for o in ocorrencias if o.get("situacao") == filtros["situacao"]]
    u = utilizador_atual()
    for o in ocorrencias:
        o["_pode_editar"] = pode_editar_ocorrencia(o, u)
    total_geral = len(db.listar_ocorrencias({}))
    hoje = datetime.now()
    semana_str = (hoje - timedelta(days=hoje.weekday())).strftime("%Y-%m-%d")
    mes_str = hoje.strftime("%Y-%m-01")
    return render_template("ocorrencias_lista.html",
                           ocorrencias=ocorrencias, filtros=filtros,
                           total_geral=total_geral,
                           semana_str=semana_str,
                           mes_str=mes_str,
                           **_opcoes())


@app.route("/ocorrencias/<int:oid>")
@login_required
def ver_ocorrencia(oid):
    o = db.obter_ocorrencia(oid)
    if not o:
        abort(404)
    ant, prox = db.anterior_proximo(oid)
    outras = db.ocorrencias_do_aluno(o.get("nome_aluno", ""), excluir_id=oid) if o.get("nome_aluno") else []
    return render_template("ocorrencia_detalhe.html", o=o,
                           pode_editar=pode_editar_ocorrencia(o, utilizador_atual()),
                           anterior=ant, proximo=prox, outras_do_aluno=outras,
                           situacoes=db.SITUACOES)


@app.route("/ocorrencias/<int:oid>/editar", methods=["GET", "POST"])
@login_required
def editar_ocorrencia(oid):
    o = db.obter_ocorrencia(oid)
    if not o:
        abort(404)
    u = utilizador_atual()
    if not pode_editar_ocorrencia(o, u):
        flash("Apenas pode editar ocorrências por si registadas.", "danger")
        return redirect(url_for("ver_ocorrencia", oid=oid))
    if request.method == "POST":
        dados = _form_para_dados()
        db.atualizar_ocorrencia(oid, dados)
        flash(f"Ocorrência nº {oid:03d} atualizada.", "success")
        return redirect(url_for("ver_ocorrencia", oid=oid))
    return render_template("ocorrencia_form.html", dados=o, numero=oid,
                           edicao=True, **_opcoes())


@app.route("/ocorrencias/<int:oid>/eliminar", methods=["POST"])
@login_required
def eliminar_ocorrencia(oid):
    o = db.obter_ocorrencia(oid)
    if not o:
        abort(404)
    u = utilizador_atual()
    if not pode_editar_ocorrencia(o, u):
        flash("Apenas pode eliminar ocorrências por si registadas.", "danger")
        return redirect(url_for("ver_ocorrencia", oid=oid))
    db.eliminar_ocorrencia(oid)
    flash(f"Ocorrência nº {oid:03d} eliminada.", "warning")
    return redirect(url_for("listar_ocorrencias"))


@app.route("/ocorrencias/<int:oid>/duplicar")
@login_required
def duplicar_ocorrencia(oid):
    o = db.obter_ocorrencia(oid)
    if not o:
        abort(404)
    u = utilizador_atual()
    dados = dict(o)
    dados["data"] = datetime.now().strftime("%Y-%m-%d")
    dados["hora"] = datetime.now().strftime("%H:%M")
    dados["colaborador"] = u["nome"]
    return render_template("ocorrencia_form.html", dados=dados,
                           numero=db.proximo_numero(), duplicado=True, **_opcoes())


@app.route("/ocorrencias/<int:oid>/imprimir")
@login_required
def imprimir_ocorrencia(oid):
    o = db.obter_ocorrencia(oid)
    if not o:
        abort(404)
    return render_template("ocorrencia_print.html", o=o)


@app.route("/ocorrencias/<int:oid>/situacao", methods=["POST"])
@coordenador_required
def mudar_situacao(oid):
    nova = request.form.get("situacao", "")
    if nova in db.SITUACOES:
        db.atualizar_situacao(oid, nova)
    return redirect(request.referrer or url_for("listar_ocorrencias"))


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------
@app.route("/estatisticas")
@coordenador_required
def estatisticas():
    periodo = request.args.get("periodo", "ano")
    ano_letivo = request.args.get("ano_letivo")
    stats = db.estatisticas(periodo=periodo, ano_letivo=ano_letivo)
    return render_template("estatisticas.html", stats=stats,
                           periodo=periodo, ano_letivo=ano_letivo)


@app.route("/estatisticas/dados")
@coordenador_required
def estatisticas_dados():
    periodo = request.args.get("periodo", "ano")
    ano_letivo = request.args.get("ano_letivo")
    return jsonify(db.estatisticas(periodo=periodo, ano_letivo=ano_letivo))


# ---------------------------------------------------------------------------
# Exportar CSV
# ---------------------------------------------------------------------------
def _gerar_csv(ocorrencias):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Ordem"] + db.CAMPOS_OCORRENCIA + ["criado_em", "criado_por"])
    for o in ocorrencias:
        w.writerow([f"{o['id']:03d}"] + [o.get(c, "") for c in db.CAMPOS_OCORRENCIA]
                   + [o.get("criado_em", ""), o.get("criado_por_nome", "")])
    return buf.getvalue().encode("utf-8-sig")


@app.route("/exportar.csv")
@coordenador_required
def exportar_csv():
    return Response(
        _gerar_csv(db.listar_ocorrencias()),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=ocorrencias_{datetime.now():%Y%m%d}.csv"},
    )


@app.route("/exportar-filtrado.csv")
@coordenador_required
def exportar_filtrado():
    filtros = {k: request.args.get(k, "").strip() for k in
               ("ciclo", "ano", "turma", "disciplina", "local", "motivo",
                "data_de", "data_ate", "texto")}
    return Response(
        _gerar_csv(db.listar_ocorrencias(filtros)),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=ocorrencias_filtrado_{datetime.now():%Y%m%d}.csv"},
    )


# ---------------------------------------------------------------------------
# Colaboradores
# ---------------------------------------------------------------------------
@app.route("/colaboradores")
@login_required
def colaboradores():
    todos = db.listar_utilizadores()
    return render_template("colaboradores.html", utilizadores=todos)


# ---------------------------------------------------------------------------
# Gestão de utilizadores (apenas Coordenador)
# ---------------------------------------------------------------------------
@app.route("/utilizadores")
@coordenador_required
def listar_utilizadores():
    utilizadores = db.listar_utilizadores()
    return render_template("utilizadores.html", utilizadores=utilizadores)


@app.route("/utilizadores/<int:uid>/perfil", methods=["POST"])
@coordenador_required
def mudar_perfil(uid):
    novo = request.form.get("perfil")
    me = utilizador_atual()
    if uid == me["id"] and novo == "Colaborador" and db.contar_coordenadores() <= 1:
        flash("Não pode despromover-se: é o único Coordenador ativo.", "danger")
        return redirect(url_for("listar_utilizadores"))
    db.alterar_perfil(uid, novo)
    flash("Perfil atualizado.", "success")
    return redirect(url_for("listar_utilizadores"))


@app.route("/utilizadores/<int:uid>/toggle", methods=["POST"])
@coordenador_required
def toggle_utilizador(uid):
    me = utilizador_atual()
    if uid == me["id"]:
        flash("Não pode desativar-se a si próprio.", "danger")
        return redirect(url_for("listar_utilizadores"))
    u = db.obter_utilizador(uid)
    if u and u["perfil"] == "Coordenador" and u["ativo"] and db.contar_coordenadores() <= 1:
        flash("Não pode desativar o único Coordenador ativo.", "danger")
        return redirect(url_for("listar_utilizadores"))
    db.alternar_ativo(uid)
    flash("Estado do utilizador atualizado.", "success")
    return redirect(url_for("listar_utilizadores"))


# ---------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def nao_encontrado(e):
    return render_template("erro.html", codigo=404,
                           mensagem="Página não encontrada."), 404


@app.errorhandler(500)
def erro_servidor(e):
    return render_template("erro.html", codigo=500,
                           mensagem="Erro interno do servidor."), 500


# ---------------------------------------------------------------------------
def _abrir_browser():
    import time
    import webbrowser
    time.sleep(1.2)
    try:
        webbrowser.open("http://localhost:5000")
    except Exception:
        pass


if __name__ == "__main__":
    app.config["ALLOW_SHUTDOWN"] = True
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Thread(target=_abrir_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
