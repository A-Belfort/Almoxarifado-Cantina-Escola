-- Dados fictícios iniciais para testes do Almoxarifado da Cantina-Escola
INSERT INTO produtos (nome, unidade, estoque_minimo, saldo)
VALUES
    ('Arroz Branco Tipo 1', 'kg', 10, 25),
    ('Feijão Carioca', 'kg', 8, 5),
    ('Óleo de Soja', 'L', 6, 6),
    ('Suco Integral de Uva', 'un', 15, 0)
ON CONFLICT (nome) DO NOTHING;
