from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Flask, jsonify, render_template, request
import psycopg2
from psycopg2 import errors
from db import get_connection

app = Flask(__name__)

# Momento em que a aplicação iniciou (usado na prova de persistência após reinício)
INICIADO_EM = datetime.now(timezone.utc).isoformat()
UNIDADES_VALIDAS = ("un", "kg", "L")
TIPOS_MOVIMENTACAO = ("entrada", "saida")


def formatar_numero(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    return valor


def ler_decimal(valor):
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite():
            return None
        return numero
    except InvalidOperation:
        return None


def serializar_produto(row):
    return {
        "id": row["id"],
        "nome": row["nome"],
        "unidade": row["unidade"],
        "estoque_minimo": formatar_numero(row["estoque_minimo"]),
        "saldo": formatar_numero(row["saldo"]),
        "criado_em": row["criado_em"].isoformat() if row.get("criado_em") else None,
    }


def serializar_movimentacao(row):
    return {
        "id": row["id"],
        "produto_id": row["produto_id"],
        "tipo": row["tipo"],
        "quantidade": formatar_numero(row["quantidade"]),
        "motivo": row["motivo"],
        "criada_em": row["criada_em"].isoformat() if row.get("criada_em") else None,
    }


@app.route("/", methods=["GET"])
def inicio():
    return jsonify({
        "servico": "Almoxarifado da Cantina-Escola",
        "status": "ativo",
        "painel_web": "/painel",
        "rotas": [
            "GET /painel",
            "GET /health",
            "POST /produtos",
            "GET /produtos",
            "GET /produtos/abaixo-minimo",
            "GET /produtos/<id>",
            "POST /produtos/<id>/movimentacoes",
        ],
    })


@app.route("/painel", methods=["GET"])
def painel():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        return jsonify({
            "status": "ok",
            "banco": "conectado",
            "iniciado_em": INICIADO_EM,
        }), 200
    except psycopg2.Error:
        return jsonify({
            "status": "indisponivel",
            "banco": "erro_conexao",
            "iniciado_em": INICIADO_EM,
        }), 503
    finally:
        if conn:
            conn.close()


@app.route("/produtos", methods=["POST"])
def cadastrar_produto():
    dados = request.get_json(silent=True) or {}

    nome = str(dados.get("nome", "")).strip()
    unidade = str(dados.get("unidade", "")).strip()
    estoque_minimo = ler_decimal(dados.get("estoque_minimo", 0))

    if not nome or len(nome) > 120:
        return jsonify({"erro": "O nome do produto é obrigatório (1 a 120 caracteres)."}), 400

    if unidade not in UNIDADES_VALIDAS:
        return jsonify({"erro": "Unidade inválida. Use 'un', 'kg' ou 'L'."}), 400

    if estoque_minimo is None or estoque_minimo < 0:
        return jsonify({"erro": "O estoque mínimo deve ser um número maior ou igual a 0."}), 400

    conn = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO produtos (nome, unidade, estoque_minimo, saldo)
                    VALUES (%s, %s, %s, 0)
                    RETURNING id, nome, unidade, estoque_minimo, saldo, criado_em;
                    """,
                    (nome, unidade, estoque_minimo),
                )
                produto = cur.fetchone()
        return jsonify(serializar_produto(produto)), 201
    except errors.UniqueViolation:
        return jsonify({"erro": "Já existe um produto cadastrado com este nome."}), 409
    finally:
        if conn:
            conn.close()


@app.route("/produtos", methods=["GET"])
def listar_produtos():
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, unidade, estoque_minimo, saldo, criado_em
                FROM produtos
                ORDER BY nome ASC;
                """
            )
            produtos = [serializar_produto(row) for row in cur.fetchall()]
        return jsonify(produtos), 200
    finally:
        if conn:
            conn.close()


@app.route("/produtos/abaixo-minimo", methods=["GET"])
def listar_abaixo_minimo():
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, unidade, estoque_minimo, saldo, criado_em
                FROM produtos
                WHERE saldo < estoque_minimo
                ORDER BY nome ASC;
                """
            )
            produtos = [serializar_produto(row) for row in cur.fetchall()]
        return jsonify(produtos), 200
    finally:
        if conn:
            conn.close()


@app.route("/produtos/<int:produto_id>", methods=["GET"])
def consultar_produto(produto_id):
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, unidade, estoque_minimo, saldo, criado_em
                FROM produtos
                WHERE id = %s;
                """,
                (produto_id,),
            )
            produto = cur.fetchone()
            if not produto:
                return jsonify({"erro": "Produto não encontrado."}), 404

            cur.execute(
                """
                SELECT id, produto_id, tipo, quantidade, motivo, criada_em
                FROM movimentacoes
                WHERE produto_id = %s
                ORDER BY criada_em DESC, id DESC;
                """,
                (produto_id,),
            )
            movimentacoes = [serializar_movimentacao(row) for row in cur.fetchall()]

        resposta = serializar_produto(produto)
        resposta["movimentacoes"] = movimentacoes
        return jsonify(resposta), 200
    finally:
        if conn:
            conn.close()


@app.route("/produtos/<int:produto_id>/movimentacoes", methods=["POST"])
def registrar_movimentacao(produto_id):
    dados = request.get_json(silent=True) or {}

    tipo = str(dados.get("tipo", "")).strip()
    quantidade = ler_decimal(dados.get("quantidade"))
    motivo = str(dados.get("motivo", "")).strip()

    if tipo not in TIPOS_MOVIMENTACAO:
        return jsonify({"erro": "Tipo inválido. Use 'entrada' ou 'saida'."}), 400

    if quantidade is None or quantidade <= 0:
        return jsonify({"erro": "A quantidade deve ser maior que zero."}), 400

    if not motivo or len(motivo) > 255:
        return jsonify({"erro": "O motivo é obrigatório (1 a 255 caracteres)."}), 400

    conn = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM produtos WHERE id = %s;", (produto_id,))
                if not cur.fetchone():
                    return jsonify({"erro": "Produto não encontrado."}), 404

                # Atualização atômica: impede saldo negativo mesmo em requisições simultâneas
                if tipo == "entrada":
                    cur.execute(
                        """
                        UPDATE produtos
                        SET saldo = saldo + %s
                        WHERE id = %s
                        RETURNING saldo;
                        """,
                        (quantidade, produto_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE produtos
                        SET saldo = saldo - %s
                        WHERE id = %s AND saldo >= %s
                        RETURNING saldo;
                        """,
                        (quantidade, produto_id, quantidade),
                    )

                atualizado = cur.fetchone()
                if not atualizado:
                    return jsonify({"erro": "Saldo insuficiente para realizar a saída."}), 409

                cur.execute(
                    """
                    INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, produto_id, tipo, quantidade, motivo, criada_em;
                    """,
                    (produto_id, tipo, quantidade, motivo),
                )
                movimentacao = cur.fetchone()

        resposta = serializar_movimentacao(movimentacao)
        resposta["saldo_atual"] = formatar_numero(atualizado["saldo"])
        return jsonify(resposta), 201
    finally:
        if conn:
            conn.close()


@app.errorhandler(404)
def nao_encontrado(_error):
    return jsonify({"erro": "Rota não encontrada."}), 404


@app.errorhandler(405)
def metodo_nao_permitido(_error):
    return jsonify({"erro": "Método HTTP não permitido."}), 405


@app.errorhandler(psycopg2.OperationalError)
def erro_conexao_banco(_error):
    return jsonify({"erro": "Serviço de banco de dados indisponível no momento."}), 503


@app.errorhandler(Exception)
def erro_interno(error):
    app.logger.exception("Erro interno não tratado: %s", error)
    return jsonify({"erro": "Erro interno no servidor."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
