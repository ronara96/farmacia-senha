import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf_farmacia_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha = {"senha": "---", "tipo": "Aguardando..."}

# --- ESTILOS CSS COMUNS (MODERNOS) ---
ESTILO_BASE = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
<style>
    body { font-family: 'Poppins', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; background: #f1f5f9; color: #1e293b; }
    .card { background: white; padding: 40px; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 600px; }
    button { cursor: pointer; transition: all 0.3s ease; border: none; font-family: 'Poppins', sans-serif; font-weight: 600; }
    button:active { transform: scale(0.95); }
</style>
"""

# --- HTML PAINEL (TV) ---
HTML_PAINEL = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Painel TV</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    {ESTILO_BASE}
    <style>
        body {{ background: #0f172a; color: white; }}
        .card {{ background: #1e293b; border: 2px solid #334155; max-width: 800px; }}
        #senha {{ font-size: 220px; color: #10b981; font-weight: 700; line-height: 1; margin: 20px 0; }}
        #tipo {{ font-size: 40px; color: #38bdf8; text-transform: uppercase; letter-spacing: 2px; }}
        .label {{ font-size: 24px; color: #94a3b8; text-transform: uppercase; }}
        .btn-som {{ position: fixed; top: 20px; right: 20px; padding: 10px 20px; background: #ef4444; border-radius: 10px; color: white; }}
    </style>
</head>
<body>
    <button class="btn-som" onclick="this.style.display='none'">🔊 ATIVAR SOM</button>
    <div class="card">
        <div class="label">Senha Atual</div>
        <div id="senha">---</div>
        <div id="tipo">AGUARDANDO...</div>
    </div>
    <script>
        var socket = io();
        var ultimaLida = "";
        function atualizarTela(data) {{
            if (data.senha !== "---" && data.senha !== ultimaLida) {{
                document.getElementById('senha').innerText = data.senha;
                document.getElementById('tipo').innerText = data.tipo;
                ultimaLida = data.senha;
                var msg = new SpeechSynthesisUtterance("Senha " + data.senha + ". " + data.tipo);
                msg.lang = 'pt-BR';
                window.speechSynthesis.speak(msg);
            }}
        }}
        socket.on('chamar_painel', atualizarTela);
        setInterval(async () => {{
            try {{ let res = await fetch('/api/estado'); let data = await res.json(); atualizarTela(data.senha_atual); }} catch(e) {{}}
        }}, 3000);
    </script>
</body>
</html>
"""

# --- HTML ATENDENTE ---
HTML_ATENDENTE = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Painel Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    {ESTILO_BASE}
    <style>
        .stats {{ display: flex; gap: 20px; justify-content: center; margin: 30px 0; }}
        .stat-box {{ background: #f8fafc; padding: 20px; border-radius: 16px; flex: 1; border: 1px solid #e2e8f0; }}
        .stat-box span {{ display: block; }}
        .stat-n {{ font-size: 32px; font-weight: 700; color: #0f172a; }}
        .stat-l {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
        .btn-call {{ background: #f97316; color: white; width: 100%; padding: 20px; font-size: 20px; border-radius: 16px; box-shadow: 0 4px 14px rgba(249, 115, 22, 0.4); }}
    </style>
</head>
<body>
    <div class="card">
        <h2 style="margin-top:0">Controle de Atendimento</h2>
        <div class="stats">
            <div class="stat-box">
                <span class="stat-l">Preferencial</span>
                <span id="p" class="stat-n">0</span>
            </div>
            <div class="stat-box">
                <span class="stat-l">Normal</span>
                <span id="n" class="stat-n">0</span>
            </div>
        </div>
        <button class="btn-call" onclick="chamar()">📢 CHAMAR PRÓXIMO</button>
    </div>
    <script>
        var socket = io();
        async function chamar() {{ await fetch('/api/chamar'); }}
        function atualizarFila(data) {{
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        }}
        socket.on('atualizar_fila', atualizarFila);
        setInterval(async () => {{
            try {{ let res = await fetch('/api/estado'); let data = await res.json(); atualizarFila(data.fila); }} catch(e) {{}}
        }}, 2000);
    </script>
</body>
</html>
"""

# --- HTML TOTEM ---
HTML_TOTEM = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Gerador de Senha</title>
    {ESTILO_BASE}
    <style>
        .btn-t {{ width: 100%; padding: 40px; margin-bottom: 20px; border-radius: 20px; font-size: 28px; color: white; }}
        .btn-green {{ background: #10b981; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4); }}
        .btn-blue {{ background: #3b82f6; box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4); }}
    </style>
</head>
<body>
    <div class="card">
        <h1 style="margin-top:0; font-size: 24px; color: #64748b;">BEM-VINDO À FARMÁCIA</h1>
        <p style="margin-bottom: 30px;">Toque abaixo para retirar sua senha</p>
        <button class="btn-t btn-green" onclick="gerar('normal')">ATENDIMENTO NORMAL</button>
        <button class="btn-t btn-blue" onclick="gerar('preferencial')">PREFERENCIAL</button>
    </div>
    <script>
        async function gerar(t) {{
            await fetch('/api/gerar?tipo=' + t);
            alert('Senha Gerada! Retire seu ticket.');
        }}
    </script>
</body>
</html>
"""

# --- LÓGICA DO SERVIDOR (MANTIDA) ---

@app.route('/')
def r_totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def r_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def r_atendente(): return render_template_string(HTML_ATENDENTE)

@app.route('/api/estado')
def api_estado():
    return jsonify({"fila": fila, "senha_atual": ultima_senha})

@app.route('/api/gerar')
def api_gerar():
    t = request.args.get('tipo', 'normal')
    s = f"{'N' if t == 'normal' else 'P'}-{contadores[t]:03d}"
    contadores[t] += 1
    fila[t].append(s)
    socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "ok"})

@app.route('/api/chamar')
def api_chamar():
    senha = None
    tipo = ""
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
        tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0)
        tipo = "Normal"
    if senha:
        ultima_senha['senha'] = senha
        ultima_senha['tipo'] = tipo
        socketio.emit('chamar_painel', ultima_senha, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
