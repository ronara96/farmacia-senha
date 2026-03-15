import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-secret-key'
# Configuração para o Render não bloquear as mensagens
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados em memória
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# --- HTML PAINEL (A TV que mostra e fala) ---
HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Painel Sigaf</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #1a1a1a; color: white; font-family: sans-serif; text-align: center; padding-top: 50px; }
        #box { border: 10px solid #444; border-radius: 30px; padding: 40px; background: #000; display: inline-block; width: 80%; }
        #senha { font-size: 180px; color: #00ff00; margin: 20px 0; }
        #tipo { font-size: 50px; color: #3498db; }
        button { padding: 15px 30px; background: #e74c3c; color: white; border: none; border-radius: 10px; cursor: pointer; font-size: 20px; }
    </style>
</head>
<body>
    <button id="btn-som" onclick="this.style.display='none'">🔊 ATIVAR SOM DO PAINEL</button>
    <div id="box">
        <h1>SENHA</h1>
        <div id="senha">---</div>
        <div id="tipo">AGUARDANDO...</div>
    </div>
    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo.toUpperCase();
            
            let voz = new SpeechSynthesisUtterance("Senha " + data.senha + ". " + data.tipo);
            voz.lang = 'pt-BR';
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(voz);
        });
    </script>
</body>
</html>
"""

# --- HTML TOTEM (Onde o cliente clica para pegar a senha) ---
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem Sigaf</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: sans-serif; padding-top: 50px; }
        button { font-size: 35px; padding: 40px; margin: 20px; width: 80%; cursor: pointer; border-radius: 20px; border: none; color: white; font-weight: bold; }
        .btn-n { background: #27ae60; }
        .btn-p { background: #2980b9; }
    </style>
</head>
<body>
    <h1>Retire sua Senha</h1>
    <button class="btn-n" onclick="gerar('normal')">ATENDIMENTO NORMAL</button>
    <button class="btn-p" onclick="gerar('preferencial')">ATENDIMENTO PREFERENCIAL</button>
    <script>
        var socket = io();
        function gerar(tipo) {
            socket.emit('solicitar_senha', {tipo: tipo});
            alert('Senha Gerada!');
        }
    </script>
</body>
</html>
"""

# --- HTML ATENDENTE (Onde o botão de chamar PRECISA funcionar) ---
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente Sigaf</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 40px; background: #f4f4f4; }
        .card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: inline-block; }
        .btn-chamar { font-size: 25px; padding: 25px 50px; background: #f39c12; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; }
        .btn-chamar:hover { background: #d35400; }
        .status { font-size: 22px; margin-bottom: 20px; color: #333; }
        span { font-weight: bold; color: #e67e22; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Controle do Atendente</h1>
        <div class="status">
            Aguardando: <span id="p">0</span> Preferencial | <span id="n">0</span> Normal
        </div>
        <button class="btn-chamar" onclick="chamar_proximo()">📢 CHAMAR PRÓXIMO</button>
    </div>
    <script>
        var socket = io();
        
        // Função que o botão clica
        function chamar_proximo() {
            console.log("Botão clicado!");
            socket.emit('proxima_senha_servidor'); // Nome único para não ter erro
        }

        socket.on('atualizar_fila', function(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        });

        socket.on('connect', function() {
            socket.emit('pedir_atualizacao');
        });
    </script>
</body>
</html>
"""

# --- LÓGICA DO SERVIDOR (PYTHON) ---

@app.route('/')
def rota_totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def rota_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def rota_atendente(): return render_template_string(HTML_ATENDENTE)

@socketio.on('solicitar_senha')
def tratar_solicitacao(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    senha = f"{prefixo}-{contadores[tipo]:03d}"
    contadores[tipo] += 1
    fila[tipo].append(senha)
    socketio.emit('atualizar_fila', fila, broadcast=True)

# AQUI ESTÁ A CORREÇÃO DO BOTÃO
@socketio.on('proxima_senha_servidor')
def tratar_chamado():
    senha_escolhida = None
    tipo_atendimento = ""
    
    # Prioridade para preferencial
    if fila['preferencial']:
        senha_escolhida = fila['preferencial'].pop(0)
        tipo_atendimento = "Preferencial"
    elif fila['normal']:
        senha_escolhida = fila['normal'].pop(0)
        tipo_atendimento = "Normal"
    
    if senha_escolhida:
        # Envia para o painel
        socketio.emit('chamar_painel', {'senha': senha_escolhida, 'tipo': tipo_atendimento}, broadcast=True)
        # Atualiza o contador de quem sobrou na fila para os atendentes
        socketio.emit('atualizar_fila', fila, broadcast=True)

@socketio.on('pedir_atualizacao')
def enviar_estado_atual():
    emit('atualizar_fila', fila)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
