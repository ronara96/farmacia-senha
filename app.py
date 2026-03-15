import eventlet
eventlet.monkey_patch()  # Essencial para o SocketIO no Render

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-secret-123'
# Configuração vital para o Render aceitar as conexões de abas diferentes
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados em memória
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- HTML PAINEL (TV) ---
HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel de Chamadas</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; background: #222; color: white; margin-top: 50px;}
        h1 { font-size: 50px; color: yellow;}
        #senhaAtual { font-size: 150px; margin: 0; color: #00ff00; }
        #tipoAtual { font-size: 40px; }
        button { padding: 20px; background: red; color: white; border: none; cursor: pointer; border-radius: 5px; }
    </style>
</head>
<body>
    <button id="btnSom" onclick="this.style.display='none'">🔊 CLIQUE PARA ATIVAR O SOM</button>
    <h1>SENHA CHAMADA:</h1>
    <div id="senhaAtual">---</div>
    <div id="tipoAtual">Aguardando...</div>

    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senhaAtual').innerText = data.senha;
            document.getElementById('tipoAtual').innerText = data.tipo.toUpperCase();
            
            // Voz em Português
            var msg = new SpeechSynthesisUtterance("Senha " + data.senha + ", " + data.tipo);
            msg.lang = 'pt-BR';
            window.speechSynthesis.cancel(); 
            window.speechSynthesis.speak(msg);
        });
    </script>
</body>
</html>
"""

# --- HTML TOTEM (BOTÃO DE SENHA) ---
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Retirar Senha</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; padding-top: 50px; }
        button { font-size: 30px; padding: 40px; margin: 20px; cursor: pointer; border-radius: 10px; width: 80%; color: white; border: none; }
        .btn-n { background-color: #4CAF50; }
        .btn-p { background-color: #2196F3; }
    </style>
</head>
<body>
    <h1>Selecione o seu atendimento:</h1>
    <button class="btn-n" onclick="pedir('normal')">NORMAL</button>
    <button class="btn-p" onclick="pedir('preferencial')">PREFERENCIAL</button>

    <script>
        var socket = io();
        function pedir(tipo) {
            socket.emit('solicitar_senha', {tipo: tipo});
            alert('Senha solicitada!');
        }
    </script>
</body>
</html>
"""

# --- HTML ATENDENTE (CHAMAR E VER QUANTIDADE) ---
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: Arial; padding: 20px; text-align: center; }
        button { font-size: 20px; padding: 15px; background: #f44336; color: white; cursor:pointer; width: 100%; max-width: 300px; border: none; border-radius: 10px; }
        .info { margin: 20px; font-size: 22px; }
        span { font-weight: bold; color: #e67e22; }
    </style>
</head>
<body>
    <h1>Painel do Atendente</h1>
    <div class="info">
        <p>Preferencial: <span id="fila-p">0</span> aguardando</p>
        <p>Normal: <span id="fila-n">0</span> aguardando</p>
    </div>
    <button onclick="chamar()">📢 Chamar Próxima Senha</button>

    <script>
        var socket = io();
        function chamar() {
            socket.emit('chamar_proximo');
        }
        // Atualiza os contadores em tempo real
        socket.on('atualizar_fila', function(data) {
            document.getElementById('fila-p').innerText = data.preferencial.length;
            document.getElementById('fila-n').innerText = data.normal.length;
        });
        // Pede os números atuais assim que abre a página
        socket.on('connect', function() {
            socket.emit('pedir_atualizacao');
        });
    </script>
</body>
</html>
"""

# --- LÓGICA DO SERVIDOR ---

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
    # Broadcast=True faz com que o Atendente veja o número mudar na hora
    socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('chamar_proximo')
def handle_chamar_proximo():
    senha_chamada = None
    tipo_chamada = ""
    
    if len(fila['preferencial']) > 0:
        senha_chamada = fila['preferencial'].pop(0)
        tipo_chamada = "Preferencial"
    elif len(fila['normal']) > 0:
        senha_chamada = fila['normal'].pop(0)
        tipo_chamada = "Normal"
    
    if senha_chamada:
        # Avisa o painel e atualiza a contagem de quem sobrou na fila
        socketio.emit('chamar_painel', {'senha': senha_chamada, 'tipo': tipo_chamada}, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('pedir_atualizacao')
def handle_pedir_atualizacao():
    emit('atualizar_fila', fila)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
