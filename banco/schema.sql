CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL UNIQUE,
    unidade VARCHAR(10) NOT NULL CHECK (unidade IN ('un', 'kg', 'L')),
    estoque_minimo NUMERIC(10, 3) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    saldo NUMERIC(10, 3) NOT NULL DEFAULT 0 CHECK (saldo >= 0),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS movimentacoes (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('entrada', 'saida')),
    quantidade NUMERIC(10, 3) NOT NULL CHECK (quantidade > 0),
    motivo VARCHAR(255) NOT NULL,
    criada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
