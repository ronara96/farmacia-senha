# 1. Preparação do servidor (Gevent é mais estável que Eventlet)
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf_farmacia_2026'
# Configuração reforçada para evitar quedas
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_timeout=60)

# Banco de dados temporário
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha = {"senha": "---", "tipo": "Aguardando..."}

# --- HTML DAS TELAS ---

# Painel (TV) com Verificação Automática
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel TV</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #0f0; font-family: sans-serif; text-align: center; padding-top: 100px; }
        #senha { font-size: 200px; font-weight: bold; }
        #tipo { font-size: 50px; color: #fff; }
    </style>
</head>
<body>
    <button onclick="this.style.display='none'" style="padding:20px;">🔊 ATIVAR SOM</button>
    <h1>SENHA:</h1>
    <div id="senha">---</div>
    <div id="tipo">AGUARDANDO...</div>

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

        // Verificação de segurança a cada 3 segundos (caso o socket caia)
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

# Atendente com Verificação Automática
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding-top: 50px; background: #f0f0f0; }
        .caixa { background: white; padding: 30px; display: inline-block; border-radius: 20px; }
        button { font-size: 30px; padding: 20px; background: orange; color: white; border: none; cursor: pointer; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="caixa">
        <h2>FILA DE ESPERA</h2>
        <p style="font-size:25px;">Preferencial: <span id="p">0</span> | Normal: <span id="n">0</span></p>
        <button onclick="chamar()">📢 CHAMAR PRÓXIMO</button>
    </div>

    <script>
        var socket = io();
        
        async function chamar() {
            await fetch('/api/chamar');
        }

        function atualizarFila(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        }

        socket.on('atualizar_fila', atualizarFila);

        // Verificação automática (NÃO PRECISA MAIS DE F5)
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

# Totem
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<body style="text-align:center; padding-top:100px;">
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
