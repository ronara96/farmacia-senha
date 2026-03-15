import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados simples
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- HTML PAINEL ---
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #0f0; font-family: sans-serif; text-align: center; padding-top: 100px; }
        #senha { font-size: 250px; font-weight: bold; }
        #tipo { font-size: 60px; color: #fff; }
    </style>
</head>
<body>
    <h1>SENHA:</h1>
    <div id="senha">---</div>
    <div id="tipo">AGUARDANDO...</div>
    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo;
            // O som agora é uma linha simples, se falhar, não trava o resto
            try {
                var msg = new SpeechSynthesisUtterance("Senha " + data.senha);
                msg.lang = 'pt-BR';
                window.speechSynthesis.speak(msg);
            } catch(e) { console.log("Erro no som"); }
        });
    </script>
</body>
</html>
"""

# --- HTML TOTEM ---
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body style="text-align:center; padding-top:100px;">
    <button onclick="gerar('normal')" style="font-size:50px; background:green; color:white; padding:50px; width:80%;">NORMAL</button><br><br>
    <button onclick="gerar('preferencial')" style="font-size:50px; background:blue; color:white; padding:50px; width:80%;">PREFERENCIAL</button>
    <script>
        var socket = io();
        function gerar(t) { socket.emit('solicitar_senha', {tipo: t}); alert('Senha Gerada!'); }
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
    <h1>FILA ATUAL</h1>
    <div style="font-size:30px; margin-bottom:30px;">
        Preferencial: <span id="p">0</span> | Normal: <span id="n">0</span>
    </div>
    <button onclick="chamar()" style="font-size:40px; padding:30px; background:orange; cursor:pointer;">📢 CHAMAR PRÓXIMO</button>
    
    <script>
        var socket = io();
        function chamar() {
            console.log("Enviando comando...");
            socket.emit('clique_chamar'); 
        }
        socket.on('atualizar_fila', function(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        });
        socket.on('connect', function() { socket.emit('pedir_status'); });
    </script>
</body>
</html>
"""

# --- LÓGICA ---

@app.route('/')
def r_totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def r_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def r_atendente(): return render_template_string(HTML_ATENDENTE)

@socketio.on('solicitar_senha')
def handle_solicitar(data):
    t = data['tipo']
    pref = 'N' if t == 'normal' else 'P'
    s = f"{pref}-{contadores[t]:03d}"
    contadores[t] += 1
    fila[t].append(s)
    socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('clique_chamar')
def handle_chamar():
    senha = None
    tipo = ""
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
        tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0)
        tipo = "Normal"
    
    if senha:
        # Primeiro atualiza os números (isso tira o número da tela do atendente)
        socketio.emit('atualizar_fila', fila, broadcast=True)
        # Depois manda o painel mostrar
        socketio.emit('chamar_painel', {'senha': senha, 'tipo': tipo}, broadcast=True)

@socketio.on('pedir_status')
def handle_status():
    emit('atualizar_fila', fila)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
