"""Camada de acesso a dados para Registo de Ocorrências GAAF.

Usa PostgreSQL quando DATABASE_URL está definido (Render/Supabase),
ou SQLite localmente.
"""
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")  # set on Render

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def get_conn():
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10,
                                options="-c search_path=gaaf")
        conn.autocommit = False
        return conn

    def _row(cur):
        """Fetch one row as dict."""
        row = cur.fetchone()
        return dict(row) if row else None

    def _rows(cur):
        return [dict(r) for r in cur.fetchall()]

    PH = "%s"  # PostgreSQL placeholder

    def _dictcur(conn):
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocorrencias.db")

    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _row(cur):
        row = cur.fetchone()
        return dict(row) if row else None

    def _rows(cur):
        return [dict(r) for r in cur.fetchall()]

    PH = "?"

    def _dictcur(conn):
        return conn.cursor()


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
    "Educação Física", "EMRC",
    "Filosofia", "Psicologia",
    "Tecnologias da Informação e Comunicação", "TIC",
    "Estudo do Meio", "Apoio ao Estudo", "Oferta Complementar",
    "Cidadania e Desenvolvimento", "Cidadania",
    "Economia", "Sociologia", "Direito",
    "Artes Visuais", "Desenho", "Geometria Descritiva",
    "Matemática A", "Matemática B", "MACS",
    "Outra",
]

PERFIS = ["Colaborador", "Coordenador"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def init_db():
    """Cria/migra tabelas. Só relevante para SQLite local."""
    if DATABASE_URL:
        return  # schema já existe no Supabase

    conn = get_conn()
    cur = _dictcur(conn)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS utilizadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('Colaborador','Coordenador')),
            pergunta_seguranca TEXT NOT NULL,
            resposta_seguranca TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            hora TEXT, ano TEXT, turma TEXT, ciclo TEXT, nome_aluno TEXT,
            colaborador TEXT, disciplina TEXT, local TEXT, contactos_ee TEXT,
            atividade_ga TEXT, motivo1 TEXT, motivo2 TEXT, com_quem TEXT,
            destruicao TEXT, descricao TEXT, observacoes TEXT,
            intervencao_gaaf TEXT, medidas_aplicadas TEXT, situacao TEXT,
            criado_em TEXT NOT NULL,
            criado_por INTEGER,
            FOREIGN KEY (criado_por) REFERENCES utilizadores(id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocorr_data ON ocorrencias(data)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocorr_ciclo ON ocorrencias(ciclo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocorr_turma ON ocorrencias(turma)")

    # Migrate old column name
    try:
        cur.execute("ALTER TABLE ocorrencias ADD COLUMN descricao TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE utilizadores ADD COLUMN resposta_seguranca TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Utilizadores
# ---------------------------------------------------------------------------
def criar_utilizador(nome, email, password, perfil, pergunta, resposta):
    conn = get_conn()
    cur = _dictcur(conn)
    try:
        cur.execute(
            f"""INSERT INTO utilizadores
               (nome,email,password_hash,perfil,pergunta_seguranca,resposta_seguranca,criado_em)
               VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
            (nome.strip(), email.strip().lower(), generate_password_hash(password),
             perfil, pergunta.strip(),
             generate_password_hash(resposta.strip().lower()),
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False, "Já existe uma conta com esse email."
        return False, str(e)
    finally:
        conn.close()


def autenticar(email, password):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        f"SELECT * FROM utilizadores WHERE email = {PH} AND ativo = 1",
        (email.strip().lower(),),
    )
    row = _row(cur)
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def obter_utilizador_por_email(email):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT * FROM utilizadores WHERE email = {PH}", (email.strip().lower(),))
    row = _row(cur)
    conn.close()
    return row


def obter_utilizador(uid):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT * FROM utilizadores WHERE id = {PH}", (uid,))
    row = _row(cur)
    conn.close()
    return row


def verificar_resposta_seguranca(email, resposta):
    u = obter_utilizador_por_email(email)
    if not u:
        return False
    return check_password_hash(u["resposta_seguranca"], resposta.strip().lower())


def atualizar_password(email, nova_password):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        f"UPDATE utilizadores SET password_hash = {PH} WHERE email = {PH}",
        (generate_password_hash(nova_password), email.strip().lower()),
    )
    conn.commit()
    conn.close()


def listar_utilizadores():
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute("SELECT id,nome,email,perfil,ativo,criado_em FROM utilizadores ORDER BY nome")
    rows = _rows(cur)
    conn.close()
    return rows


def alterar_perfil(uid, novo_perfil):
    if novo_perfil not in PERFIS:
        return
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"UPDATE utilizadores SET perfil = {PH} WHERE id = {PH}", (novo_perfil, uid))
    conn.commit()
    conn.close()


def alternar_ativo(uid):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"UPDATE utilizadores SET ativo = 1 - ativo WHERE id = {PH}", (uid,))
    conn.commit()
    conn.close()


def contar_coordenadores():
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute("SELECT COUNT(*) AS n FROM utilizadores WHERE perfil = 'Coordenador' AND ativo = 1")
    n = cur.fetchone()["n"]
    conn.close()
    return n


def atualizar_utilizador(uid, nome):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"UPDATE utilizadores SET nome = {PH} WHERE id = {PH}", (nome.strip(), uid))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Ocorrências
# ---------------------------------------------------------------------------
CAMPOS_OCORRENCIA = [
    "data", "hora", "ano", "turma", "ciclo", "nome_aluno", "colaborador",
    "disciplina", "local", "contactos_ee", "atividade_ga",
    "motivo1", "motivo2", "com_quem", "destruicao", "descricao", "observacoes",
    "intervencao_gaaf", "medidas_aplicadas", "situacao",
]


def criar_ocorrencia(dados, criado_por):
    conn = get_conn()
    cur = _dictcur(conn)
    cols = CAMPOS_OCORRENCIA + ["criado_em", "criado_por"]
    valores = [dados.get(c, "") for c in CAMPOS_OCORRENCIA]
    valores.append(datetime.now().isoformat(timespec="seconds"))
    valores.append(criado_por)
    ph = ",".join([PH] * len(cols))
    if DATABASE_URL:
        cur.execute(
            f"INSERT INTO ocorrencias ({','.join(cols)}) VALUES ({ph}) RETURNING id",
            valores,
        )
        novo_id = cur.fetchone()["id"]
    else:
        cur.execute(
            f"INSERT INTO ocorrencias ({','.join(cols)}) VALUES ({ph})",
            valores,
        )
        novo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return novo_id


def atualizar_ocorrencia(oid, dados):
    conn = get_conn()
    cur = _dictcur(conn)
    sets = ",".join(f"{c}={PH}" for c in CAMPOS_OCORRENCIA)
    valores = [dados.get(c, "") for c in CAMPOS_OCORRENCIA] + [oid]
    cur.execute(f"UPDATE ocorrencias SET {sets} WHERE id={PH}", valores)
    conn.commit()
    conn.close()


def eliminar_ocorrencia(oid):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"DELETE FROM ocorrencias WHERE id={PH}", (oid,))
    conn.commit()
    conn.close()


def obter_ocorrencia(oid):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        f"""SELECT o.*, u.nome AS criado_por_nome
           FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por
           WHERE o.id = {PH}""",
        (oid,),
    )
    row = _row(cur)
    conn.close()
    return row


def listar_ocorrencias(filtros=None):
    filtros = filtros or {}
    where = []
    params = []
    for campo in ("ciclo", "ano", "turma", "disciplina", "local", "situacao"):
        v = filtros.get(campo)
        if v:
            where.append(f"o.{campo} = {PH}")
            params.append(v)
    if filtros.get("motivo"):
        where.append(f"(o.motivo1 = {PH} OR o.motivo2 = {PH})")
        params.extend([filtros["motivo"], filtros["motivo"]])
    if filtros.get("data_de"):
        where.append(f"o.data >= {PH}")
        params.append(filtros["data_de"])
    if filtros.get("data_ate"):
        where.append(f"o.data <= {PH}")
        params.append(filtros["data_ate"])
    if filtros.get("texto"):
        like = f"%{filtros['texto']}%"
        where.append(f"(o.nome_aluno ILIKE {PH} OR o.observacoes ILIKE {PH} OR o.colaborador ILIKE {PH})" if DATABASE_URL
                     else f"(o.nome_aluno LIKE {PH} OR o.observacoes LIKE {PH} OR o.colaborador LIKE {PH})")
        params.extend([like, like, like])

    sql = """SELECT o.*, u.nome AS criado_por_nome
             FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.data DESC, o.id DESC"

    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(sql, params)
    rows = _rows(cur)
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------
def _contar_por(coluna, where_sql="", params=()):
    conn = get_conn()
    cur = _dictcur(conn)
    if DATABASE_URL:
        nullif_expr = f"COALESCE(NULLIF({coluna},''),'(sem valor)')"
    else:
        nullif_expr = f"COALESCE(NULLIF({coluna},''),'(sem valor)')"
    sql = f"""SELECT {nullif_expr} AS chave, COUNT(*) AS n
              FROM ocorrencias {where_sql}
              GROUP BY chave ORDER BY n DESC, chave"""
    cur.execute(sql, params)
    rows = [(r["chave"], r["n"]) for r in cur.fetchall()]
    conn.close()
    return rows


def estatisticas(periodo=None, ano_letivo=None):
    where = ""
    params = ()
    hoje = datetime.now()

    if periodo == "mes":
        primeiro = hoje.replace(day=1).strftime("%Y-%m-%d")
        where = f"WHERE data >= {PH}"
        params = (primeiro,)
    elif periodo == "semestre":
        mes = hoje.month
        if 9 <= mes <= 12 or mes == 1:
            inicio = datetime(hoje.year if mes >= 9 else hoje.year - 1, 9, 1)
        else:
            inicio = datetime(hoje.year, 2, 1)
        where = f"WHERE data >= {PH}"
        params = (inicio.strftime("%Y-%m-%d"),)
    elif periodo == "ano" and ano_letivo:
        inicio = f"{ano_letivo}-09-01"
        fim = f"{int(ano_letivo)+1}-08-31"
        where = f"WHERE data BETWEEN {PH} AND {PH}"
        params = (inicio, fim)
    elif periodo == "ano":
        ano = hoje.year if hoje.month >= 9 else hoje.year - 1
        inicio = f"{ano}-09-01"
        fim = f"{ano+1}-08-31"
        where = f"WHERE data BETWEEN {PH} AND {PH}"
        params = (inicio, fim)

    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT COUNT(*) AS n FROM ocorrencias {where}", params)
    total = cur.fetchone()["n"]
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


def _motivos_combinados(where_sql="", params=()):
    conn = get_conn()
    cur = _dictcur(conn)
    sql = f"""
        SELECT motivo, COUNT(*) AS n FROM (
            SELECT motivo1 AS motivo FROM ocorrencias {where_sql}
            UNION ALL
            SELECT motivo2 AS motivo FROM ocorrencias {where_sql}
        ) AS m WHERE motivo IS NOT NULL AND motivo != ''
        GROUP BY motivo ORDER BY n DESC, motivo
    """
    cur.execute(sql, params + params)
    rows = [(r["motivo"], r["n"]) for r in cur.fetchall()]
    conn.close()
    return rows


def _por_mes(where_sql="", params=()):
    conn = get_conn()
    cur = _dictcur(conn)
    if DATABASE_URL:
        sql = f"""SELECT to_char(data::date,'YYYY-MM') AS mes, COUNT(*) AS n
                  FROM ocorrencias {where_sql}
                  GROUP BY mes ORDER BY mes"""
    else:
        sql = f"""SELECT substr(data,1,7) AS mes, COUNT(*) AS n
                  FROM ocorrencias {where_sql}
                  GROUP BY mes ORDER BY mes"""
    cur.execute(sql, params)
    rows = [(r["mes"], r["n"]) for r in cur.fetchall()]
    conn.close()
    return rows


def contar_hoje():
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT COUNT(*) AS n FROM ocorrencias WHERE data = {PH}", (hoje,))
    n = cur.fetchone()["n"]
    conn.close()
    return n


def contar_semana():
    from datetime import timedelta
    hoje = datetime.now().date()
    segunda = hoje - timedelta(days=hoje.weekday())
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT COUNT(*) AS n FROM ocorrencias WHERE data >= {PH}",
                (segunda.strftime("%Y-%m-%d"),))
    n = cur.fetchone()["n"]
    conn.close()
    return n


def contar_mes():
    hoje = datetime.now()
    mes_inicio = hoje.strftime("%Y-%m-01")
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT COUNT(*) AS n FROM ocorrencias WHERE data >= {PH}", (mes_inicio,))
    n = cur.fetchone()["n"]
    conn.close()
    return n


def listar_ocorrencias_recentes(n=5):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        f"""SELECT o.id, o.data, o.nome_aluno, o.motivo1, o.ciclo, o.ano, o.turma,
                  o.situacao, u.nome AS criado_por_nome
           FROM ocorrencias o LEFT JOIN utilizadores u ON u.id = o.criado_por
           ORDER BY o.id DESC LIMIT {PH}""",
        (n,),
    )
    rows = _rows(cur)
    conn.close()
    return rows


def listar_nomes_alunos():
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        "SELECT DISTINCT nome_aluno FROM ocorrencias "
        "WHERE nome_aluno IS NOT NULL AND nome_aluno != '' ORDER BY nome_aluno"
    )
    rows = [r["nome_aluno"] for r in cur.fetchall()]
    conn.close()
    return rows


def anterior_proximo(oid):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"SELECT id FROM ocorrencias WHERE id < {PH} ORDER BY id DESC LIMIT 1", (oid,))
    ant = cur.fetchone()
    cur.execute(f"SELECT id FROM ocorrencias WHERE id > {PH} ORDER BY id ASC LIMIT 1", (oid,))
    prox = cur.fetchone()
    conn.close()
    return (ant["id"] if ant else None, prox["id"] if prox else None)


def ocorrencias_do_aluno(nome_aluno, excluir_id=None):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(
        f"SELECT id, data, motivo1, situacao FROM ocorrencias WHERE nome_aluno = {PH} ORDER BY data DESC LIMIT 10",
        (nome_aluno,),
    )
    result = _rows(cur)
    conn.close()
    if excluir_id:
        result = [r for r in result if r["id"] != excluir_id]
    return result


def atualizar_situacao(oid, situacao):
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute(f"UPDATE ocorrencias SET situacao = {PH} WHERE id = {PH}", (situacao, oid))
    conn.commit()
    conn.close()


def proximo_numero():
    conn = get_conn()
    cur = _dictcur(conn)
    cur.execute("SELECT COALESCE(MAX(id),0)+1 AS n FROM ocorrencias")
    n = cur.fetchone()["n"]
    conn.close()
    return n
