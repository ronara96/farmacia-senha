import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- HTML PAINEL (TV) ---
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="background:#000; color:#0f0; text-align:center; font-family:sans-serif;">
    <h1>SENHA:</h1>
    <div id="senha" style="font-size:150px;">---</div>
    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            var msg = new SpeechSynthesisUtterance("Senha " + data.senha);
            window.speechSynthesis.speak(msg);
        });
    </script>
</body>
</html>
"""

# --- HTML ATENDENTE (MUDANÇA TOTAL NO BOTÃO) ---
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="text-align:center; font-family:sans-serif; padding-top:50px;">
    <h2>Aguardando: <span id="p">0</span> P | <span id="n">0</span> N</h2>
    <br>
    <button onclick="chamarViaHttp()" style="font-size:40px; padding:30px; background:orange; cursor:pointer;">
        📢 CHAMAR PRÓXIMO
    </button>
    
    <script>
        var socket = io();
        
        function chamarViaHttp() {
            console.log("Chamando via HTTP...");
            fetch('/api/chamar') // Envia um sinal direto para o servidor
            .then(response => console.log("Sinal enviado!"));
        }

        socket.on('atualizar_fila', function(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        });
    </script>
</body>
</html>
"""

# --- LÓGICA DO SERVIDOR ---

@app.route('/')
def r_totem(): return render_template_string("""
    <button onclick="io().emit('solicitar_senha', {tipo:'normal'})" style="padding:40px; font-size:30px;">NORMAL</button>
    <button onclick="io().emit('solicitar_senha', {tipo:'preferencial'})" style="padding:40px; font-size:30px;">PREFERENCIAL</button>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
""")

@app.route('/painel')
def r_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def r_atendente(): return render_template_string(HTML_ATENDENTE)

# NOVA ROTA DE EMERGÊNCIA PARA O BOTÃO
@app.route('/api/chamar')
def api_chamar():
    senha = None
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
    elif fila['normal']:
        senha = fila['normal'].pop(0)
    
    if senha:
        socketio.emit('chamar_painel', {'senha': senha}, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "ok"})

@socketio.on('solicitar_senha')
def handle_solicitar(data):
    t = data['tipo']
    s = f"{'N' if t == 'normal' else 'P'}-{contadores[t]:03d}"
    contadores[t] += 1
    fila[t].append(s)
    socketio.emit('atualizar_fila', fila, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
