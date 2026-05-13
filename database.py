"""Camada de acesso a dados para Registo de Ocorrências GAAF.

SUPABASE_URL definida → Supabase REST API (HTTPS, sem problemas IPv6 no Render)
Sem SUPABASE_URL → SQLite local
"""
import os
from collections import Counter
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ---------------------------------------------------------------------------
# Listas de valores
# ---------------------------------------------------------------------------
CICLOS = ["1º", "2º", "3º", "SEC"]
ANOS = ["1º", "2º", "3º", "4º", "5º", "6º",
        "7º", "8º", "9º", "10º", "11º", "12º"]
LOCAIS = ["Sala de aula", "Exterior", "Pavilhão", "Refeitório",
          "Biblioteca", "Bar", "Corredor", "Casa de banho", "Outro"]
COM_QUEM = ["Professor(a)", "Colega", "Elemento da comunidade escolar"]
DESTRUICAO = ["", "De colegas", "Equipamento escolar"]
CONTACTOS_EE = ["", "Sim", "Não"]
MOTIVOS = [
    "Incumprimento de regras",
    "Falta de respeito para com o(a) professor(a)",
    "Falta de respeito para com o(a) colega",
    "Falta de respeito para com elemento da comunidade escolar",
    "Linguagem imprópria para com o(a) professor(a)",
    "Linguagem imprópria para com o(a) colega",
    "Linguagem imprópria para com elemento da comunidade escolar",
    "Agressão física",
    "Agressão psicológica",
    "Agressão física/psicológica",
    "Utilização de objetos não permitidos",
    "Utilização de substâncias não permitidas",
    "Destruição de bens",
    "Destruição de materiais",
    "Utilização indevida do smartphone",
    "Utilização indevida da tecnologia",
    "Outra situação",
]
SITUACOES = [
    "Em análise",
    "Em curso",
    "Encaminhado para Direção de Turma",
    "Encaminhado para Direção",
    "Encaminhado para CPCJ",
    "Resolvido",
    "Arquivado",
]
DISCIPLINAS = [
    "Português", "Matemática", "Inglês", "Francês", "Espanhol", "Alemão",
    "História", "Geografia", "História e Geografia de Portugal",
    "Ciências Naturais", "Ciências Físico-Químicas", "Físico-Química",
    "Biologia", "Química", "Biologia e Geologia",
    "Educação Visual", "Educação Tecnológica", "Educação Musical",
    "Educação Física", "EMRC", "Filosofia", "Psicologia",
    "Tecnologias da Informação e Comunicação", "TIC",
    "Estudo do Meio", "Apoio ao Estudo", "Oferta Complementar",
    "Cidadania e Desenvolvimento", "Cidadania",
    "Economia", "Sociologia", "Direito",
    "Artes Visuais", "Desenho", "Geometria Descritiva",
    "Matemática A", "Matemática B", "MACS", "Outra",
]
PERFIS = ["Colaborador", "Coordenador"]

CAMPOS_OCORRENCIA = [
    "data", "hora", "ano", "turma", "ciclo", "nome_aluno", "colaborador",
    "disciplina", "local", "contactos_ee", "atividade_ga",
    "motivo1", "motivo2", "com_quem", "destruicao", "descricao", "observacoes",
    "intervencao_gaaf", "medidas_aplicadas", "situacao",
]


# ===========================================================================
# MODO PRODUÇÃO — Supabase REST API
# ===========================================================================
if SUPABASE_URL:
    import requests as _rq

    _BASE = SUPABASE_URL.rstrip("/") + "/rest/v1"

    def _h(prefer=None):
        h = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "gaaf",
            "Content-Profile": "gaaf",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _get(table, params=None):
        r = _rq.get(f"{_BASE}/{table}", headers=_h(), params=params or [], timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(table, data):
        r = _rq.post(f"{_BASE}/{table}", headers=_h("return=representation"), json=data, timeout=10)
        r.raise_for_status()
        d = r.json()
        return d[0] if isinstance(d, list) else d

    def _patch(table, where, data):
        r = _rq.patch(f"{_BASE}/{table}", headers=_h("return=minimal"), params=where, json=data, timeout=10)
        r.raise_for_status()

    def _delete(table, where):
        r = _rq.delete(f"{_BASE}/{table}", headers=_h(), params=where, timeout=10)
        r.raise_for_status()

    def _count_q(table, params):
        h = {**_h(), "Prefer": "count=exact"}
        r = _rq.get(f"{_BASE}/{table}", headers=h, params=params + [("select", "id")], timeout=10)
        cr = r.headers.get("Content-Range", "0-0/0")
        return int(cr.split("/")[1]) if "/" in cr else 0

    def _nr(row):
        """Normaliza None → '' em campos de texto; adiciona criado_por_nome."""
        if row is None:
            return None
        for k in list(row.keys()):
            if row[k] is None and k not in ("id", "criado_por", "ativo"):
                row[k] = ""
        row.setdefault("criado_por_nome", row.get("colaborador", ""))
        return row

    def _nrs(rows):
        return [_nr(r) for r in rows]

    # -----------------------------------------------------------------------
    # Schema / init
    # -----------------------------------------------------------------------
    def init_db():
        pass  # tabelas já existem no Supabase

    def get_conn():
        raise NotImplementedError("Usar REST API em produção")

    # -----------------------------------------------------------------------
    # Utilizadores
    # -----------------------------------------------------------------------
    def criar_utilizador(nome, email, password, perfil, pergunta, resposta):
        try:
            _post("utilizadores", {
                "nome": nome.strip(),
                "email": email.strip().lower(),
                "password_hash": generate_password_hash(password),
                "perfil": perfil,
                "pergunta_seguranca": pergunta.strip(),
                "resposta_seguranca": generate_password_hash(resposta.strip().lower()),
                "criado_em": datetime.now().isoformat(timespec="seconds"),
                "ativo": 1,
            })
            return True, None
        except Exception as e:
            msg = str(e)
            if "unique" in msg.lower() or "23505" in msg:
                return False, "Já existe uma conta com esse email."
            return False, msg

    def autenticar(email, password):
        rows = _get("utilizadores", [("email", f"eq.{email.strip().lower()}"), ("ativo", "eq.1")])
        if not rows:
            return None
        row = rows[0]
        if check_password_hash(row["password_hash"], password):
            return _nr(row)
        return None

    def obter_utilizador_por_email(email):
        rows = _get("utilizadores", [("email", f"eq.{email.strip().lower()}")])
        return _nr(rows[0]) if rows else None

    def obter_utilizador(uid):
        rows = _get("utilizadores", [("id", f"eq.{uid}")])
        return _nr(rows[0]) if rows else None

    def verificar_resposta_seguranca(email, resposta):
        u = obter_utilizador_por_email(email)
        if not u:
            return False
        return check_password_hash(u["resposta_seguranca"], resposta.strip().lower())

    def atualizar_password(email, nova_password):
        _patch("utilizadores", [("email", f"eq.{email.strip().lower()}")],
               {"password_hash": generate_password_hash(nova_password)})

    def listar_utilizadores():
        return _nrs(_get("utilizadores", [("select", "id,nome,email,perfil,ativo,criado_em"), ("order", "nome.asc")]))

    def alterar_perfil(uid, novo_perfil):
        if novo_perfil not in PERFIS:
            return
        _patch("utilizadores", [("id", f"eq.{uid}")], {"perfil": novo_perfil})

    def alternar_ativo(uid):
        u = obter_utilizador(uid)
        if u:
            _patch("utilizadores", [("id", f"eq.{uid}")], {"ativo": 0 if u["ativo"] else 1})

    def contar_coordenadores():
        return _count_q("utilizadores", [("perfil", "eq.Coordenador"), ("ativo", "eq.1")])

    def atualizar_utilizador(uid, nome):
        _patch("utilizadores", [("id", f"eq.{uid}")], {"nome": nome.strip()})

    # -----------------------------------------------------------------------
    # Ocorrências
    # -----------------------------------------------------------------------
    def criar_ocorrencia(dados, criado_por):
        payload = {c: dados.get(c, "") for c in CAMPOS_OCORRENCIA}
        payload["criado_em"] = datetime.now().isoformat(timespec="seconds")
        payload["criado_por"] = criado_por
        result = _post("ocorrencias", payload)
        return result["id"]

    def atualizar_ocorrencia(oid, dados):
        payload = {c: dados.get(c, "") for c in CAMPOS_OCORRENCIA}
        _patch("ocorrencias", [("id", f"eq.{oid}")], payload)

    def eliminar_ocorrencia(oid):
        _delete("ocorrencias", [("id", f"eq.{oid}")])

    def obter_ocorrencia(oid):
        rows = _get("ocorrencias", [("id", f"eq.{oid}")])
        if not rows:
            return None
        row = rows[0]
        u = obter_utilizador(row.get("criado_por")) if row.get("criado_por") else None
        row["criado_por_nome"] = u["nome"] if u else row.get("colaborador", "")
        return _nr(row)

    def listar_ocorrencias(filtros=None):
        filtros = filtros or {}
        params = [("order", "data.desc,id.desc")]
        for campo in ("ciclo", "ano", "turma", "disciplina", "local", "situacao"):
            v = filtros.get(campo)
            if v:
                params.append((campo, f"eq.{v}"))
        if filtros.get("data_de"):
            params.append(("data", f"gte.{filtros['data_de']}"))
        if filtros.get("data_ate"):
            params.append(("data", f"lte.{filtros['data_ate']}"))
        if filtros.get("motivo"):
            m = filtros["motivo"].replace("'", "''")
            params.append(("or", f"(motivo1.eq.{m},motivo2.eq.{m})"))
        if filtros.get("texto"):
            t = filtros["texto"].replace("'", "''")
            params.append(("or", f"(nome_aluno.ilike.*{t}*,observacoes.ilike.*{t}*,colaborador.ilike.*{t}*)"))
        return _nrs(_get("ocorrencias", params))

    def listar_ocorrencias_recentes(n=5):
        rows = _get("ocorrencias", [
            ("select", "id,data,nome_aluno,motivo1,ciclo,ano,turma,situacao,colaborador"),
            ("order", "id.desc"),
            ("limit", str(n)),
        ])
        return _nrs(rows)

    def proximo_numero():
        rows = _get("ocorrencias", [("select", "id"), ("order", "id.desc"), ("limit", "1")])
        return (rows[0]["id"] + 1) if rows else 1

    def anterior_proximo(oid):
        ant = _get("ocorrencias", [("id", f"lt.{oid}"), ("select", "id"), ("order", "id.desc"), ("limit", "1")])
        prox = _get("ocorrencias", [("id", f"gt.{oid}"), ("select", "id"), ("order", "id.asc"), ("limit", "1")])
        return (ant[0]["id"] if ant else None, prox[0]["id"] if prox else None)

    def ocorrencias_do_aluno(nome_aluno, excluir_id=None):
        rows = _get("ocorrencias", [
            ("nome_aluno", f"eq.{nome_aluno}"),
            ("select", "id,data,motivo1,situacao"),
            ("order", "data.desc"),
            ("limit", "10"),
        ])
        if excluir_id:
            rows = [r for r in rows if r["id"] != excluir_id]
        return rows

    def atualizar_situacao(oid, situacao):
        _patch("ocorrencias", [("id", f"eq.{oid}")], {"situacao": situacao})

    def listar_nomes_alunos():
        rows = _get("ocorrencias", [
            ("select", "nome_aluno"),
            ("nome_aluno", "neq."),
            ("order", "nome_aluno.asc"),
        ])
        seen = set()
        result = []
        for r in rows:
            n = r.get("nome_aluno", "")
            if n and n not in seen:
                seen.add(n)
                result.append(n)
        return result

    # -----------------------------------------------------------------------
    # Contadores
    # -----------------------------------------------------------------------
    def contar_hoje():
        return _count_q("ocorrencias", [("data", f"eq.{datetime.now().strftime('%Y-%m-%d')}")])

    def contar_semana():
        segunda = (datetime.now().date() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        return _count_q("ocorrencias", [("data", f"gte.{segunda}")])

    def contar_mes():
        return _count_q("ocorrencias", [("data", f"gte.{datetime.now().strftime('%Y-%m-01')}")])

    # -----------------------------------------------------------------------
    # Estatísticas (agregação em Python — dataset pequeno)
    # -----------------------------------------------------------------------
    def _filtros_periodo(periodo, ano_letivo):
        hoje = datetime.now()
        f = {}
        if periodo == "mes":
            f["data_de"] = hoje.replace(day=1).strftime("%Y-%m-%d")
        elif periodo == "semestre":
            mes = hoje.month
            if 9 <= mes <= 12 or mes == 1:
                ano_ini = hoje.year if mes >= 9 else hoje.year - 1
                f["data_de"] = f"{ano_ini}-09-01"
            else:
                f["data_de"] = f"{hoje.year}-02-01"
        elif periodo == "ano":
            ano = int(ano_letivo) if ano_letivo else (hoje.year if hoje.month >= 9 else hoje.year - 1)
            f["data_de"] = f"{ano}-09-01"
            f["data_ate"] = f"{ano + 1}-08-31"
        return f

    def _agg(rows, campo):
        c = Counter()
        for r in rows:
            v = r.get(campo) or "(sem valor)"
            if v:
                c[v] += 1
        return sorted(c.items(), key=lambda x: (-x[1], x[0]))

    def _motivos_combinados_py(rows):
        c = Counter()
        for r in rows:
            for m in (r.get("motivo1"), r.get("motivo2")):
                if m:
                    c[m] += 1
        return sorted(c.items(), key=lambda x: (-x[1], x[0]))

    def _por_mes_py(rows):
        c = Counter()
        for r in rows:
            d = r.get("data", "")
            if d and len(d) >= 7:
                c[d[:7]] += 1
        return sorted(c.items())

    def estatisticas(periodo=None, ano_letivo=None):
        rows = listar_ocorrencias(_filtros_periodo(periodo, ano_letivo))
        return {
            "total": len(rows),
            "por_ciclo": _agg(rows, "ciclo"),
            "por_ano": _agg(rows, "ano"),
            "por_turma": _agg(rows, "turma"),
            "por_disciplina": _agg(rows, "disciplina"),
            "por_local": _agg(rows, "local"),
            "por_motivo": _motivos_combinados_py(rows),
            "por_mes": _por_mes_py(rows),
        }


# ===========================================================================
# MODO LOCAL — SQLite
# ===========================================================================
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocorrencias.db")

    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS utilizadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                perfil TEXT NOT NULL CHECK (perfil IN ('Colaborador','Coordenador')),
                pergunta_seguranca TEXT NOT NULL,
                resposta_seguranca TEXT NOT NULL DEFAULT '',
                criado_em TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ocorrencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL, hora TEXT, ano TEXT, turma TEXT, ciclo TEXT,
                nome_aluno TEXT, colaborador TEXT, disciplina TEXT, local TEXT,
                contactos_ee TEXT, atividade_ga TEXT, motivo1 TEXT, motivo2 TEXT,
                com_quem TEXT, destruicao TEXT, descricao TEXT, observacoes TEXT,
                intervencao_gaaf TEXT, medidas_aplicadas TEXT, situacao TEXT,
                criado_em TEXT NOT NULL,
                criado_por INTEGER,
                FOREIGN KEY (criado_por) REFERENCES utilizadores(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ocorr_data ON ocorrencias(data)")
        # Migrações
        for col, defval in [("descricao", "TEXT"), ("resposta_seguranca", "TEXT DEFAULT ''")]:
            try:
                cur.execute(f"ALTER TABLE ocorrencias ADD COLUMN {col} TEXT")
            except Exception:
                pass
            try:
                cur.execute(f"ALTER TABLE utilizadores ADD COLUMN resposta_seguranca TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def _row(cur):
        r = cur.fetchone()
        return dict(r) if r else None

    def _rows(cur):
        return [dict(r) for r in cur.fetchall()]

    def criar_utilizador(nome, email, password, perfil, pergunta, resposta):
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO utilizadores (nome,email,password_hash,perfil,pergunta_seguranca,resposta_seguranca,criado_em) VALUES (?,?,?,?,?,?,?)",
                (nome.strip(), email.strip().lower(), generate_password_hash(password),
                 perfil, pergunta.strip(), generate_password_hash(resposta.strip().lower()),
                 datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, "Já existe uma conta com esse email."
        finally:
            conn.close()

    def autenticar(email, password):
        conn = get_conn()
        row = conn.execute("SELECT * FROM utilizadores WHERE email = ? AND ativo = 1", (email.strip().lower(),)).fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], password):
            return dict(row)
        return None

    def obter_utilizador_por_email(email):
        conn = get_conn()
        row = conn.execute("SELECT * FROM utilizadores WHERE email = ?", (email.strip().lower(),)).fetchone()
        conn.close()
        return dict(row) if row else None

    def obter_utilizador(uid):
        conn = get_conn()
        row = conn.execute("SELECT * FROM utilizadores WHERE id = ?", (uid,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def verificar_resposta_seguranca(email, resposta):
        u = obter_utilizador_por_email(email)
        if not u:
            return False
        return check_password_hash(u.get("resposta_seguranca") or u.get("resposta_hash", ""), resposta.strip().lower())

    def atualizar_password(email, nova_password):
        conn = get_conn()
        conn.execute("UPDATE utilizadores SET password_hash = ? WHERE email = ?",
                     (generate_password_hash(nova_password), email.strip().lower()))
        conn.commit()
        conn.close()

    def listar_utilizadores():
        conn = get_conn()
        rows = conn.execute("SELECT id,nome,email,perfil,ativo,criado_em FROM utilizadores ORDER BY nome").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def alterar_perfil(uid, novo_perfil):
        if novo_perfil not in PERFIS:
            return
        conn = get_conn()
        conn.execute("UPDATE utilizadores SET perfil = ? WHERE id = ?", (novo_perfil, uid))
        conn.commit()
        conn.close()

    def alternar_ativo(uid):
        conn = get_conn()
        conn.execute("UPDATE utilizadores SET ativo = 1 - ativo WHERE id = ?", (uid,))
        conn.commit()
        conn.close()

    def contar_coordenadores():
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM utilizadores WHERE perfil = 'Coordenador' AND ativo = 1").fetchone()[0]
        conn.close()
        return n

    def atualizar_utilizador(uid, nome):
        conn = get_conn()
        conn.execute("UPDATE utilizadores SET nome = ? WHERE id = ?", (nome.strip(), uid))
        conn.commit()
        conn.close()

    def criar_ocorrencia(dados, criado_por):
        conn = get_conn()
        cols = CAMPOS_OCORRENCIA + ["criado_em", "criado_por"]
        valores = [dados.get(c, "") for c in CAMPOS_OCORRENCIA]
        valores += [datetime.now().isoformat(timespec="seconds"), criado_por]
        cur = conn.execute(f"INSERT INTO ocorrencias ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", valores)
        novo_id = cur.lastrowid
        conn.commit()
        conn.close()
        return novo_id

    def atualizar_ocorrencia(oid, dados):
        conn = get_conn()
        sets = ",".join(f"{c}=?" for c in CAMPOS_OCORRENCIA)
        valores = [dados.get(c, "") for c in CAMPOS_OCORRENCIA] + [oid]
        conn.execute(f"UPDATE ocorrencias SET {sets} WHERE id=?", valores)
        conn.commit()
        conn.close()

    def eliminar_ocorrencia(oid):
        conn = get_conn()
        conn.execute("DELETE FROM ocorrencias WHERE id=?", (oid,))
        conn.commit()
        conn.close()

    def obter_ocorrencia(oid):
        conn = get_conn()
        row = conn.execute(
            "SELECT o.*, u.nome AS criado_por_nome FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por WHERE o.id = ?", (oid,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def listar_ocorrencias(filtros=None):
        filtros = filtros or {}
        where, params = [], []
        for campo in ("ciclo", "ano", "turma", "disciplina", "local", "situacao"):
            v = filtros.get(campo)
            if v:
                where.append(f"o.{campo} = ?")
                params.append(v)
        if filtros.get("motivo"):
            where.append("(o.motivo1 = ? OR o.motivo2 = ?)")
            params.extend([filtros["motivo"], filtros["motivo"]])
        if filtros.get("data_de"):
            where.append("o.data >= ?")
            params.append(filtros["data_de"])
        if filtros.get("data_ate"):
            where.append("o.data <= ?")
            params.append(filtros["data_ate"])
        if filtros.get("texto"):
            like = f"%{filtros['texto']}%"
            where.append("(o.nome_aluno LIKE ? OR o.observacoes LIKE ? OR o.colaborador LIKE ?)")
            params.extend([like, like, like])
        sql = "SELECT o.*, u.nome AS criado_por_nome FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY o.data DESC, o.id DESC"
        conn = get_conn()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def listar_ocorrencias_recentes(n=5):
        conn = get_conn()
        rows = conn.execute(
            "SELECT o.id,o.data,o.nome_aluno,o.motivo1,o.ciclo,o.ano,o.turma,o.situacao,u.nome AS criado_por_nome FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por ORDER BY o.id DESC LIMIT ?", (n,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def proximo_numero():
        conn = get_conn()
        n = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM ocorrencias").fetchone()[0]
        conn.close()
        return n

    def anterior_proximo(oid):
        conn = get_conn()
        ant = conn.execute("SELECT id FROM ocorrencias WHERE id < ? ORDER BY id DESC LIMIT 1", (oid,)).fetchone()
        prox = conn.execute("SELECT id FROM ocorrencias WHERE id > ? ORDER BY id ASC LIMIT 1", (oid,)).fetchone()
        conn.close()
        return (ant[0] if ant else None, prox[0] if prox else None)

    def ocorrencias_do_aluno(nome_aluno, excluir_id=None):
        conn = get_conn()
        rows = conn.execute("SELECT id,data,motivo1,situacao FROM ocorrencias WHERE nome_aluno = ? ORDER BY data DESC LIMIT 10", (nome_aluno,)).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        if excluir_id:
            result = [r for r in result if r["id"] != excluir_id]
        return result

    def atualizar_situacao(oid, situacao):
        conn = get_conn()
        conn.execute("UPDATE ocorrencias SET situacao = ? WHERE id = ?", (situacao, oid))
        conn.commit()
        conn.close()

    def listar_nomes_alunos():
        conn = get_conn()
        rows = conn.execute("SELECT DISTINCT nome_aluno FROM ocorrencias WHERE nome_aluno IS NOT NULL AND nome_aluno != '' ORDER BY nome_aluno").fetchall()
        conn.close()
        return [r[0] for r in rows]

    def contar_hoje():
        hoje = datetime.now().strftime("%Y-%m-%d")
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM ocorrencias WHERE data = ?", (hoje,)).fetchone()[0]
        conn.close()
        return n

    def contar_semana():
        hoje = datetime.now().date()
        segunda = hoje - timedelta(days=hoje.weekday())
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM ocorrencias WHERE data >= ?", (segunda.strftime("%Y-%m-%d"),)).fetchone()[0]
        conn.close()
        return n

    def contar_mes():
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM ocorrencias WHERE data >= ?", (datetime.now().strftime("%Y-%m-01"),)).fetchone()[0]
        conn.close()
        return n

    def _contar_por(coluna, where_sql="", params=()):
        conn = get_conn()
        sql = f"SELECT COALESCE(NULLIF({coluna},''),'(sem valor)') AS chave, COUNT(*) AS n FROM ocorrencias {where_sql} GROUP BY chave ORDER BY n DESC, chave"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [(r["chave"], r["n"]) for r in rows]

    def _motivos_combinados(where_sql="", params=()):
        conn = get_conn()
        sql = f"SELECT motivo, COUNT(*) AS n FROM (SELECT motivo1 AS motivo FROM ocorrencias {where_sql} UNION ALL SELECT motivo2 AS motivo FROM ocorrencias {where_sql}) WHERE motivo IS NOT NULL AND motivo != '' GROUP BY motivo ORDER BY n DESC, motivo"
        rows = conn.execute(sql, params + params).fetchall()
        conn.close()
        return [(r["motivo"], r["n"]) for r in rows]

    def _por_mes(where_sql="", params=()):
        conn = get_conn()
        rows = conn.execute(f"SELECT substr(data,1,7) AS mes, COUNT(*) AS n FROM ocorrencias {where_sql} GROUP BY mes ORDER BY mes", params).fetchall()
        conn.close()
        return [(r["mes"], r["n"]) for r in rows]

    def estatisticas(periodo=None, ano_letivo=None):
        where, params = "", ()
        hoje = datetime.now()
        if periodo == "mes":
            where = "WHERE data >= ?"
            params = (hoje.replace(day=1).strftime("%Y-%m-%d"),)
        elif periodo == "semestre":
            mes = hoje.month
            if 9 <= mes <= 12 or mes == 1:
                ano_ini = hoje.year if mes >= 9 else hoje.year - 1
                inicio = datetime(ano_ini, 9, 1)
            else:
                inicio = datetime(hoje.year, 2, 1)
            where = "WHERE data >= ?"
            params = (inicio.strftime("%Y-%m-%d"),)
        elif periodo == "ano":
            ano = int(ano_letivo) if ano_letivo else (hoje.year if hoje.month >= 9 else hoje.year - 1)
            where = "WHERE data BETWEEN ? AND ?"
            params = (f"{ano}-09-01", f"{ano + 1}-08-31")
        conn = get_conn()
        total = conn.execute(f"SELECT COUNT(*) FROM ocorrencias {where}", params).fetchone()[0]
        conn.close()
        return {
            "total": total,
            "por_ciclo": _contar_por("ciclo", where, params),
            "por_ano": _contar_por("ano", where, params),
            "por_turma": _contar_por("turma", where, params),
            "por_disciplina": _contar_por("disciplina", where, params),
            "por_local": _contar_por("local", where, params),
            "por_motivo": _motivos_combinados(where, params),
            "por_mes": _por_mes(where, params),
        }
