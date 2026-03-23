"""
Estrutura Oficial — Pasta Digital do Colaborador
Rezende Energia

Define a estrutura de pastas e documentos conforme o documento oficial.
Usado pelo sistema de admissão para organizar documentação.
"""

ESTRUTURA_PASTA_COLABORADOR = {
    "01_DOCUMENTOS_PESSOAIS": {
        "label": "📁 01. DOCUMENTOS PESSOAIS",
        "subpastas": {
            "01_PESSOAL": {
                "label": "📁 01 — Pessoal",
                "documentos": [
                    "Currículo",
                    "2 Fotos 3x4",
                    "CTPS + Relatório Digital",
                    "CPF",
                    "Comprovante de Regularização do CPF",
                    "RG",
                    "PIS",
                    "Cartão SUS",
                    "Cartão de Vacina Atualizado",
                    "Comprovante de Residência",
                    "Certificado de Alistamento Militar",
                    "CNH (quando exigido)",
                    "Título de Eleitor",
                    "Histórico ou Declaração Escolar",
                    "Certidão de Nascimento ou Casamento",
                    "Documentos do Cônjuge (CPF, RG, SUS)",
                    "Fator RH",
                    "Certificações da Área",
                    "Contato de Emergência",
                ],
            },
            "02_DEPENDENTES": {
                "label": "📁 02 — Dependentes (0 a 14 anos)",
                "obs": "Criar uma subpasta para cada dependente",
                "documentos": [
                    "CPF",
                    "Certidão de Nascimento ou RG",
                    "Frequência Escolar (acima de 7 anos)",
                    "Carteira de Vacinação (abaixo de 7 anos)",
                    "Cartão SUS",
                ],
            },
            "03_DADOS_BANCARIOS_E_PIX": {
                "label": "📁 03 — Dados Bancários e PIX",
                "documentos": [
                    "Comprovante de Chave PIX",
                ],
            },
        },
    },
    "02_ADMISSAO": {
        "label": "📁 02. ADMISSÃO",
        "subpastas": {
            "01_DOCUMENTO_DA_CONTABILIDADE": {
                "label": "📁 01 — Documento da Contabilidade",
                "documentos": [
                    "Ficha Registro",
                    "Contrato",
                    "Declaração de Vale-Transporte",
                    "Registro no eSocial",
                ],
            },
            "02_DOCUMENTOS_ASSINADOS": {
                "label": "📁 02 — Documentos Assinados",
                "documentos": [
                    "Ficha de Registro Assinada",
                    "Contrato de Trabalho Assinado",
                    "Declaração de Vale-Transporte",
                    "eSocial",
                    "Declaração Étnico-Racial",
                ],
            },
            "03_SAUDE_OCUPACIONAL": {
                "label": "📁 03 — Saúde Ocupacional",
                "documentos": [
                    "ASO Admissional",
                    "ASO Periódico",
                    "ASO Retorno ao Trabalho",
                    "ASO Mudança de Função",
                    "ASO Demissional",
                    "Atestados Médicos",
                    "Documentação de Afastamento INSS",
                ],
            },
        },
    },
    "04_MOBILIZACAO": {
        "label": "📁 04. MOBILIZAÇÃO",
        "subpastas": {
            "01_TREINAMENTOS": {
                "label": "📁 01 — Treinamentos",
                "documentos": [
                    "NR-10 Básico — Certificado de Formação",
                    "NR-10 SEP — Certificado de Formação",
                    "NR-35 — Certificado de Formação",
                    "Curso Rede de Distribuição",
                    "Certificados Reconhecidos (MEC quando aplicável)",
                    "NR-10 Básico — RECICLAGEM",
                    "NR-10 SEP — RECICLAGEM",
                    "NR-35 — RECICLAGEM",
                    "Ordem de Serviço",
                    "Ordem de Serviço Assinada",
                    "Integração",
                    "POP da Função",
                    "Carta de Autorização",
                ],
            },
            "03_EPI_E_CAUTELAS": {
                "label": "📁 03 — EPI e Cautelas",
                "documentos": [
                    "Ficha de Entrega de EPI",
                    "Termo de Responsabilidade (Cautela)",
                    "Controle de Substituição de EPI",
                    "Cautela de Ferramentas",
                    "Cautela de Equipamentos",
                ],
            },
            "04_OCORRENCIAS": {
                "label": "📁 04 — Ocorrências",
                "documentos": [
                    "CAT",
                    "Relatório de Acidente",
                    "Investigação de Incidente",
                ],
            },
        },
    },
    "05_TRABALHISTA_FINANCEIRO": {
        "label": "📁 05. TRABALHISTA / FINANCEIRO",
        "subpastas": {
            "01_CARTAO_PONTO_DIGITAL": {"label": "📁 01 — Cartão/Ponto Digital",   "documentos": []},
            "02_HOLERITES":            {"label": "📁 02 — Holerites / Contra-Cheque", "documentos": []},
            "03_COMPROVANTES_PAGAMENTO":{"label": "📁 03 — Comprovantes de Pagamento","documentos": []},
            "04_FERIAS":               {"label": "📁 04 — Férias",                 "documentos": []},
        },
    },
    "06_DISCIPLINAR": {
        "label": "📁 06. DISCIPLINAR",
        "subpastas": {
            "06_DISCIPLINAR": {
                "label": "📁 06 — Disciplinar",
                "documentos": [
                    "Advertências",
                    "Suspensões",
                    "Termos de Ciência",
                    "Relatórios Internos",
                ],
            },
        },
    },
}


def get_estrutura_flat():
    """Retorna lista plana de todas as pastas e documentos para exibição em UI."""
    itens = []
    for pasta_key, pasta in ESTRUTURA_PASTA_COLABORADOR.items():
        itens.append({"tipo": "pasta_raiz", "key": pasta_key, "label": pasta["label"]})
        for sub_key, sub in pasta.get("subpastas", {}).items():
            itens.append({"tipo": "subpasta", "key": sub_key, "label": sub["label"],
                          "obs": sub.get("obs", "")})
            for doc in sub.get("documentos", []):
                itens.append({"tipo": "documento", "label": doc, "pasta": sub_key})
    return itens


def get_documentos_por_pasta(pasta_key: str):
    """Retorna documentos de uma subpasta específica."""
    for pasta in ESTRUTURA_PASTA_COLABORADOR.values():
        for sub_key, sub in pasta.get("subpastas", {}).items():
            if sub_key == pasta_key:
                return sub.get("documentos", [])
    return []
