import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'senha-secreta'
# O cors_allowed_origins="*" é o que permite as telas conversarem entre si no Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados temporário (se reiniciar o Render, a fila zera)
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- TELA DO TOTEM (Onde o cliente clica) ---
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Retirar Senha</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; padding-top: 50px; }
        button { font-size: 30px; padding: 30px; margin: 20px; cursor: pointer; border-radius: 10px; width: 80%; }
        .btn-n { background-color: #4CAF50; color: white; }
        .btn-p { background-color: #2196F3; color: white; }
    </style>
</head>
<body>
    <h1>Selecione o seu atendimento:</h1>
    <button class="btn-n" onclick="pedirSenha('normal')">NORMAL</button>
    <button class="btn-p" onclick="pedirSenha('preferencial')">PREFERENCIAL</button>

    <script>
        var socket = io();
        function pedirSenha(tipo) {
            socket.emit('solicitar_senha', {tipo: tipo});
            alert('Senha solicitada!');
        }
    </script>
</body>
</html>
"""

# --- TELA DO PAINEL (A que fica na TV) ---
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel de Chamadas</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; background: #222; color: white; margin-top: 100px;}
        h1 { font-size: 50px; color: yellow;}
        #senhaAtual { font-size: 150px; margin: 0; }
        #tipoAtual { font-size: 40px; }
    </style>
</head>
<body>
    <h1>SENHA CHAMADA:</h1>
    <div id="senhaAtual">---</div>
    <div id="tipoAtual">Aguardando...</div>

    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senhaAtual').innerText = data.senha;
            document.getElementById('tipoAtual').innerText = data.tipo.toUpperCase();
            
            // Tentativa original de som (que o navegador costuma bloquear)
            var synth = window.speechSynthesis;
            var utterThis = new SpeechSynthesisUtterance("Senha " + data.senha);
            synth.speak(utterThis);
        });
    </script>
</body>
</html>
"""

# --- TELA DO ATENDENTE (Onde vê a fila e clica) ---
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: Arial; padding: 20px; text-align: center; }
        button { font-size: 20px; padding: 15px; background: #f44336; color: white; cursor:pointer; width: 100%; max-width: 300px; }
        .info { margin: 20px; font-size: 18px; }
    </style>
</head>
<body>
    <h1>Painel do Atendente</h1>
    <div class="info">
        <p>Preferencial: <span id="fila-p">0</span> aguardando</p>
        <p>Normal: <span id="fila-n">0</span> aguardando</p>
    </div>
    <button onclick="chamarProximo()">📢 Chamar Próxima Senha</button>

    <script>
        var socket = io();
        function chamarProximo() {
            socket.emit('chamar_proximo');
        }
        socket.on('atualizar_fila', function(data) {
            document.getElementById('fila-p').innerText = data.preferencial.length;
            document.getElementById('fila-n').innerText = data.normal.length;
        });
    </script>
</body>
</html>
"""

@app.route('/')
def totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def atendente(): return render_template_string(HTML_ATENDENTE)

@socketio.on('solicitar_senha')
def handle_solicitar_senha(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    numero_senha = f"{prefixo}-{contadores[tipo]:03d}"
    contadores[tipo] += 1
    fila[tipo].append(numero_senha)
    # Avisa todo mundo que a fila aumentou
    socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('chamar_proximo')
def handle_chamar_proximo():
    senha_chamada = None
    tipo_chamada = ""
    
    # Lógica de prioridade original
    if len(fila['preferencial']) > 0:
        senha_chamada = fila['preferencial'].pop(0)
        tipo_chamada = "Preferencial"
    elif len(fila['normal']) > 0:
        senha_chamada = fila['normal'].pop(0)
        tipo_chamada = "Normal"
    
    if senha_chamada:
        # Envia a senha para o Painel da TV
        socketio.emit('chamar_painel', {'senha': senha_chamada, 'tipo': tipo_chamada}, broadcast=True)
        # Atualiza os contadores na tela do atendente
        socketio.emit('atualizar_fila', fila, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
