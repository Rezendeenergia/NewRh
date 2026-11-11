"""
Gera um PDF com todas as candidaturas à CIPA, uma por página, no mesmo
formato do comprovante que o candidato vê na hora de se inscrever —
usado pelo RH para auditoria anual.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def _quebrar_linhas(texto: str, largura_max: int) -> list:
    """Quebra um texto em várias linhas pra caber na largura da página
    (quebra simples por palavra, sem depender de nenhuma lib de layout)."""
    palavras = str(texto or "").split()
    linhas, atual = [], ""
    for palavra in palavras:
        candidata = f"{atual} {palavra}".strip()
        if len(candidata) > largura_max:
            if atual:
                linhas.append(atual)
            atual = palavra
        else:
            atual = candidata
    if atual:
        linhas.append(atual)
    return linhas or [""]


def gerar_pdf_candidaturas(candidaturas: list) -> io.BytesIO:
    """Recebe uma lista de models.CipaCandidatura e devolve um BytesIO
    com um PDF: uma página por candidatura, campos iguais ao comprovante
    mostrado ao candidato (protocolo, nome, matrícula, cargo, motivo, gestão,
    data) — sem nenhum dado que não esteja já na própria candidatura."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    margem = 2.5 * cm

    if not candidaturas:
        c.setFont("Helvetica", 12)
        c.drawString(margem, altura - margem, "Nenhuma candidatura encontrada.")
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    for candidatura in candidaturas:
        y = altura - margem

        c.setFillColor(colors.HexColor("#c0392b"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margem, y, "Comprovante de Candidatura à CIPA")
        y -= 0.9 * cm

        c.setStrokeColor(colors.HexColor("#c0392b"))
        c.line(margem, y, largura - margem, y)
        y -= 1.0 * cm

        c.setFillColor(colors.black)
        campos = [
            ("Protocolo",  f"#{candidatura.id}"),
            ("Nome",       candidatura.nome),
            ("Matrícula",  candidatura.matricula),
            ("Cargo",      candidatura.cargo),
            ("Gestão",     candidatura.gestao),
            ("Recebido em", candidatura.created_at.strftime("%d/%m/%Y %H:%M") if candidatura.created_at else "—"),
        ]
        for rotulo, valor in campos:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(margem, y, f"{rotulo}:")
            c.setFont("Helvetica", 10)
            c.drawString(margem + 3.5 * cm, y, str(valor or "—"))
            y -= 0.7 * cm

        y -= 0.3 * cm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margem, y, "Por que quer participar da CIPA:")
        y -= 0.6 * cm
        c.setFont("Helvetica", 10)
        for linha in _quebrar_linhas(candidatura.motivo, 95):
            c.drawString(margem, y, linha)
            y -= 0.55 * cm

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer
