import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-secret-key'
# Adicionei o logger para você conseguir ver o que acontece nos logs do Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- HTML PAINEL ---
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="background:#000; color:#0f0; text-align:center; font-family:sans-serif; padding-top:100px;">
    <h1>SENHA:</h1>
    <div id="senha" style="font-size:200px;">---</div>
    <div id="tipo" style="font-size:50px; color:#fff;">AGUARDANDO...</div>
    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo;
            try {
                var msg = new SpeechSynthesisUtterance("Senha " + data.senha);
                msg.lang = 'pt-BR';
                window.speechSynthesis.speak(msg);
            } catch(e) {}
        });
    </script>
</body>
</html>
"""

# --- HTML ATENDENTE ---
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="text-align:center; font-family:sans-serif; padding-top:50px;">
    <h2>Senhas Aguardando</h2>
    <div style="font-size:25px;">Preferencial: <span id="p">0</span> | Normal: <span id="n">0</span></div>
    <br>
    <button id="btnChamar" style="font-size:40px; padding:30px; background:orange; color:white; border:none; border-radius:15px; cursor:pointer;">
        📢 CHAMAR PRÓXIMO
    </button>
    
    <script>
        var socket = io();
        
        // Forma mais segura de capturar o clique no navegador
        document.getElementById('btnChamar').addEventListener('click', function() {
            console.log("Botão pressionado!");
            socket.emit('proximo_evento');
        });

        socket.on('atualizar_fila', function(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        });

        socket.on('connect', function() {
            socket.emit('solicitar_status');
        });
    </script>
</body>
</html>
"""

# --- LÓGICA DO SERVIDOR ---

@app.route('/')
def r_totem(): return render_template_string("""
    <button onclick="io().emit('solicitar_senha', {tipo:'normal'})" style="padding:50px; font-size:40px; background:green; color:white;">NORMAL</button>
    <button onclick="io().emit('solicitar_senha', {tipo:'preferencial'})" style="padding:50px; font-size:40px; background:blue; color:white;">PREFERENCIAL</button>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
""")

@app.route('/painel')
def r_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def r_atendente(): return render_template_string(HTML_ATENDENTE)

@socketio.on('solicitar_senha')
def handle_solicitar(data):
    t = data['tipo']
    s = f"{'N' if t == 'normal' else 'P'}-{contadores[t]:03d}"
    contadores[t] += 1
    fila[t].append(s)
    socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('proximo_evento')
def handle_proximo():
    senha = None
    tipo = ""
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
        tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0)
        tipo = "Normal"
    
    if senha:
        # Envia para todos
        socketio.emit('chamar_painel', {'senha': senha, 'tipo': tipo}, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('solicitar_status')
def handle_status():
    socketio.emit('atualizar_fila', fila)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
