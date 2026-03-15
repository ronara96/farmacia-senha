import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf_farmacia_2026'
# Usando eventlet novamente, que é o que o Render já instalou com sucesso
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha = {"senha": "---", "tipo": "Aguardando..."}

# --- HTML (Com o "F5 Automático" que te prometi) ---

HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel TV</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="background:#000; color:#0f0; text-align:center; font-family:sans-serif; padding-top:100px;">
    <button onclick="this.style.display='none'" style="padding:20px;">🔊 ATIVAR SOM</button>
    <h1 style="font-size:50px;">SENHA:</h1>
    <div id="senha" style="font-size:200px; font-weight:bold;">---</div>
    <div id="tipo" style="font-size:50px; color:#fff;">AGUARDANDO...</div>

    <script>
        var socket = io();
        var ultimaLida = "";

        function atualizarTela(data) {
            if (data.senha !== "---" && data.senha !== ultimaLida) {
                document.getElementById('senha').innerText = data.senha;
                document.getElementById('tipo').innerText = data.tipo;
                ultimaLida = data.senha;
                var msg = new SpeechSynthesisUtterance("Senha " + data.senha);
                window.speechSynthesis.speak(msg);
            }
        }
        socket.on('chamar_painel', atualizarTela);
        setInterval(async () => {
            try {
                let res = await fetch('/api/estado');
                let data = await res.json();
                atualizarTela(data.senha_atual);
            } catch(e) {}
        }, 3000);
    </script>
</body>
</html>
"""

HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="text-align:center; font-family:sans-serif; padding-top:50px; background:#f0f0f0;">
    <div style="background:white; padding:30px; display:inline-block; border-radius:20px;">
        <h2>FILA DE ESPERA</h2>
        <p style="font-size:25px;">Preferencial: <span id="p">0</span> | Normal: <span id="n">0</span></p>
        <button onclick="chamar()" style="font-size:30px; padding:20px; background:orange; color:white; border:none; border-radius:10px; cursor:pointer;">📢 CHAMAR PRÓXIMO</button>
    </div>
    <script>
        var socket = io();
        async function chamar() { await fetch('/api/chamar'); }
        function atualizarFila(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        }
        socket.on('atualizar_fila', atualizarFila);
        setInterval(async () => {
            try {
                let res = await fetch('/api/estado');
                let data = await res.json();
                atualizarFila(data.fila);
            } catch(e) {}
        }, 2000);
    </script>
</body>
</html>
"""

HTML_TOTEM = """
<!DOCTYPE html>
<html>
<body style="text-align:center; padding-top:100px;">
    <h1>Retirar Senha</h1>
    <button onclick="gerar('normal')" style="font-size:40px; background:green; color:white; padding:40px; width:80%;">NORMAL</button><br><br>
    <button onclick="gerar('preferencial')" style="font-size:40px; background:blue; color:white; padding:40px; width:80%;">PREFERENCIAL</button>
    <script>
        async function gerar(t) {
            await fetch('/api/gerar?tipo=' + t);
            alert('Senha Gerada!');
        }
    </script>
</body>
</html>
"""

# --- ROTAS ---

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
