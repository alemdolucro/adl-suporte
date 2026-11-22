#!/usr/bin/env python3
"""Painel de licenças do ADL Suporte (Além do Lucro).

Lê os computadores registrados no banco do servidor e grava licencas.txt,
que o servidor consulta antes de permitir cada conexão.
Variáveis: ADL_PAINEL_SENHA (obrigatória), ADL_PAINEL_USUARIO (padrão esney),
ADL_DADOS (padrão /root), ADL_PAINEL_PORTA (padrão 8090).
"""
import base64
import datetime as dt
import hmac
import html
import json
import os
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DADOS = os.environ.get("ADL_DADOS", "/root")
ARQ_LIC = os.path.join(DADOS, "licencas.txt")
ARQ_DB = os.path.join(DADOS, "db_v2.sqlite3")
USUARIO = os.environ.get("ADL_PAINEL_USUARIO", "esney")
SENHA = os.environ.get("ADL_PAINEL_SENHA", "")
PORTA = int(os.environ.get("ADL_PAINEL_PORTA", "8090"))
BLOQUEADO = "2000-01-01"
NOME_TESTE = "Periodo de teste"


def hoje():
    return dt.datetime.now(dt.timezone.utc).date()


def ler_licencas():
    lic = {}
    try:
        with open(ARQ_LIC, encoding="utf-8") as f:
            for linha in f:
                p = [x.strip() for x in linha.strip().split(";")]
                if p and p[0]:
                    lic[p[0]] = {"vence": p[1] if len(p) > 1 else "", "nome": p[2] if len(p) > 2 else ""}
    except FileNotFoundError:
        pass
    return lic


def gravar_licencas(lic):
    tmp = ARQ_LIC + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for i, d in sorted(lic.items(), key=lambda x: x[1]["nome"].lower()):
            nome = d["nome"].replace(";", ",").replace("\n", " ")
            f.write(f"{i};{d['vence']};{nome}\n")
    os.replace(tmp, ARQ_LIC)


def ler_computadores():
    pcs = {}
    if not os.path.exists(ARQ_DB):
        return pcs
    try:
        con = sqlite3.connect(f"file:{ARQ_DB}?mode=ro", uri=True, timeout=5)
        for pid, criado, info in con.execute("select id, created_at, info from peer"):
            ip = ""
            try:
                ip = json.loads(info or "{}").get("ip", "")
            except ValueError:
                pass
            pcs[pid] = {"criado": str(criado or "")[:10], "ip": str(ip).replace("::ffff:", "")}
        con.close()
    except sqlite3.Error:
        pass
    return pcs


def somar_meses(data, meses):
    m = data.month - 1 + meses
    ano, mes = data.year + m // 12, m % 12 + 1
    dias = [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return dt.date(ano, mes, min(data.day, dias[mes - 1]))


def br(data_iso):
    try:
        return dt.date.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except ValueError:
        return data_iso or "-"


def situacao(vence):
    if not vence:
        return "sem", "Sem licença"
    try:
        d = dt.date.fromisoformat(vence)
    except ValueError:
        return "sem", "Sem licença"
    if d.year <= 2000:
        return "bloqueada", "Bloqueada"
    falta = (d - hoje()).days
    if falta < 0:
        return "vencida", f"Vencida em {br(vence)}"
    if falta <= 30:
        return "vencendo", f"Vence em {br(vence)} ({falta} dias)"
    return "ativa", f"Ativa até {br(vence)}"


CSS = """
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:#F4F8FF;color:#0F1B2D}
header{background:linear-gradient(135deg,#00244F 0%,#003575 55%,#0068FF 140%);color:#fff;padding:28px 32px}
header small{letter-spacing:.14em;text-transform:uppercase;color:#8FBEFF;font-size:12px}
header h1{margin:6px 0 0;font-family:Poppins,Inter,sans-serif;font-weight:600;font-size:24px}
main{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}
.card{background:#fff;border:1px solid #DCE5F2;border-radius:10px;padding:16px}
.card b{display:block;font-size:28px;color:#003575}.card span{color:#5B6B82;font-size:13px}
section{background:#fff;border:1px solid #DCE5F2;border-radius:10px;padding:18px;margin-bottom:20px;overflow-x:auto}
h2{font-family:Poppins,Inter,sans-serif;font-weight:600;color:#003575;font-size:18px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid #DCE5F2;vertical-align:middle}
th{color:#5B6B82;font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.tag{display:inline-block;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:500;white-space:nowrap}
.ativa{background:#E3F4EC;color:#1E8E5A}.bloqueada{background:#EEF1F5;color:#5B6B82}.vencendo{background:#FFF4DC;color:#9A6A00}.vencida,.sem{background:#FBE7E3;color:#C2412D}
form{display:inline-flex;gap:6px;align-items:center;margin:2px 0}
input,select{border:1px solid #DCE5F2;border-radius:8px;padding:7px 9px;font:inherit;font-size:13px}
button{border:0;border-radius:8px;padding:7px 12px;font:inherit;font-size:13px;cursor:pointer;background:#0068FF;color:#fff}
button.sec{background:#fff;color:#003575;border:1px solid #DCE5F2}button.perigo{background:#fff;color:#C2412D;border:1px solid #F1C9C0}
.id{font-family:ui-monospace,Menlo,monospace;font-weight:600}.mut{color:#5B6B82;font-size:12px}
.aviso{background:#E8F1FF;border:1px solid #C9DDFF;color:#003575;border-radius:10px;padding:12px 14px;margin-bottom:16px;font-size:14px}
"""


def pagina(msg=""):
    lic = ler_licencas()
    pcs = ler_computadores()
    ids = sorted(set(pcs) | set(lic), key=lambda i: (lic.get(i, {}).get("nome", "~").lower(), i))
    cont = {"ativa": 0, "vencendo": 0, "vencida": 0, "sem": 0, "bloqueada": 0, "teste": 0}
    linhas = []
    for i in ids:
        d = lic.get(i, {"vence": "", "nome": ""})
        cls, txt = situacao(d["vence"])
        teste = d["nome"] == NOME_TESTE
        cont["teste" if teste and cls in ("ativa", "vencendo") else cls] += 1
        if teste and cls in ("ativa", "vencendo"):
            txt = txt.replace("Ativa até", "Em teste até").replace("Vence em", "Teste acaba em")
        p = pcs.get(i, {})
        e = html.escape
        acoes = (
            f'<form method="post"><input type="hidden" name="id" value="{e(i)}">'
            f'<input name="nome" placeholder="Cliente" value="{"" if teste else e(d["nome"])}" style="width:150px">'
            f'<input name="meses" type="number" min="1" max="36" value="12" list="prazos" style="width:70px" title="Meses"> meses'
            f'<button name="acao" value="ativar">{"Renovar" if d["vence"] and not teste and cls != "bloqueada" else "Ativar"}</button></form> '
        )
        if d["vence"] and cls != "bloqueada":
            acoes += (
                f'<form method="post" onsubmit="return confirm(\'Bloquear {e(i)}?\')">'
                f'<input type="hidden" name="id" value="{e(i)}"><button class="perigo" name="acao" value="bloquear">Bloquear</button></form>'
            )
        linhas.append(
            f"<tr><td><span class='id'>{e(i)}</span><br><span class='mut'>{'Período de teste' if teste else (e(d['nome']) or 'sem nome')}</span></td>"
            f"<td>{e(p.get('ip', '')) or '-'}<br><span class='mut'>registrado em {br(p.get('criado', ''))}</span></td>"
            f"<td><span class='tag {cls}'>{e(txt)}</span></td><td>{acoes}</td></tr>"
        )
    aviso = f'<div class="aviso">{html.escape(msg)}</div>' if msg else ""
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Licenças ADL Suporte</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><small>ADL Tech</small><h1>Licenças do ADL Suporte</h1></header><main>{aviso}
<div class="cards"><div class="card"><b>{cont['ativa']}</b><span>Licenças ativas</span></div>
<div class="card"><b>{cont['vencendo']}</b><span>Vencendo em 30 dias</span></div>
<div class="card"><b>{cont['vencida']}</b><span>Vencidas</span></div>
<div class="card"><b>{cont['teste']}</b><span>Em teste (30 dias)</span></div>
<div class="card"><b>{cont['sem'] + cont['bloqueada']}</b><span>Sem licença ou bloqueados</span></div></div>
<section><h2>Ativar um computador pelo ID</h2><p class="mut" style="margin:-6px 0 10px">Todo computador novo entra com 30 dias de teste automaticamente. Ao ativar, a licença passa a contar a partir de hoje.</p><p class="mut" style="margin:-6px 0 10px">Escolha qualquer prazo de 1 a 36 meses (por exemplo 3, 5, 9 ou 12). Na renovação, os meses são somados ao vencimento atual.</p>
<form method="post"><input name="id" placeholder="ID do computador" required style="width:170px">
<input name="nome" placeholder="Nome do cliente" required style="width:220px">
<input name="meses" type="number" min="1" max="36" value="12" list="prazos" style="width:70px" title="Meses"> meses
<datalist id="prazos"><option value="1"><option value="3"><option value="5"><option value="6"><option value="9"><option value="12"><option value="24"></datalist>
<button name="acao" value="ativar">Ativar licença</button></form></section>
<section><h2>Computadores</h2><table><thead><tr><th>ID e cliente</th><th>Origem</th><th>Licença</th><th>Ações</th></tr></thead>
<tbody>{''.join(linhas) or '<tr><td colspan=4>Nenhum computador registrado ainda.</td></tr>'}</tbody></table></section>
<p class="mut">ADL Suporte, baseado no RustDesk (AGPL-3.0). Além do Lucro.</p></main></body></html>"""


class Painel(BaseHTTPRequestHandler):
    def autorizado(self):
        if not SENHA:
            return False
        cab = self.headers.get("Authorization", "")
        if not cab.startswith("Basic "):
            return False
        try:
            u, _, s = base64.b64decode(cab[6:]).decode("utf-8").partition(":")
        except ValueError:
            return False
        return hmac.compare_digest(u, USUARIO) and hmac.compare_digest(s, SENHA)

    def pedir_login(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Licencas ADL Suporte", charset="UTF-8"')
        self.end_headers()

    def responder(self, corpo, codigo=200):
        b = corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if not self.autorizado():
            return self.pedir_login()
        if self.path.startswith("/api/licencas"):
            corpo = json.dumps({"licencas": ler_licencas(), "computadores": ler_computadores()}, ensure_ascii=False)
            b = corpo.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            return self.wfile.write(b)
        msg = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("msg", [""])[0]
        self.responder(pagina(msg))

    def do_POST(self):
        if not self.autorizado():
            return self.pedir_login()
        n = min(int(self.headers.get("Content-Length", "0") or 0), 10000)
        f = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
        g = lambda k: (f.get(k, [""])[0] or "").strip()
        pid, acao = g("id").replace(" ", ""), g("acao")
        lic = ler_licencas()
        msg = ""
        if not pid.isalnum() or len(pid) > 30:
            msg = "ID inválido."
        elif acao == "ativar":
            meses = int(g("meses")) if g("meses").isdigit() else 12
            meses = max(1, min(meses, 36))
            atual = lic.get(pid, {})
            base = hoje()
            try:
                v = dt.date.fromisoformat(atual.get("vence", ""))
                if v > base and atual.get("nome") != NOME_TESTE:
                    base = v
            except ValueError:
                pass
            nova = somar_meses(base, meses)
            lic[pid] = {"vence": nova.isoformat(), "nome": g("nome") or atual.get("nome", "")}
            gravar_licencas(lic)
            msg = f"Licença de {pid} válida até {br(nova.isoformat())}."
        elif acao == "bloquear":
            atual = lic.get(pid, {})
            lic[pid] = {"vence": BLOQUEADO, "nome": atual.get("nome", "")}
            gravar_licencas(lic)
            msg = f"{pid} bloqueado."
        self.send_response(303)
        self.send_header("Location", "/?msg=" + urllib.parse.quote(msg))
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    if not SENHA:
        raise SystemExit("Defina ADL_PAINEL_SENHA")
    print(f"Painel de licenças na porta {PORTA}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORTA), Painel).serve_forever()
