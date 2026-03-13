from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import os

# Inicialização do App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'senha-secreta-farmacia'

# Configuração robusta para evitar bloqueios de Firewall
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet', 
    ping_timeout=60, 
    ping_interval=25
)

# Banco de dados temporário em memória
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# Mock de Impressora
def imprimir_senha_termica(senha, tipo):
    print(f"\n[IMPRESSORA TÉRMICA] Imprimindo: {senha} ({tipo})\n")

# --- FRONTEND INTEGRADO ---

HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem - Farmácia</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: sans-serif; background: #f0f2f5; padding-top: 50px; }
        .btn { font-size: 28px; padding: 40px; margin: 15px; width: 80%; max-width: 400px; 
               border: none; border-radius: 15px; cursor: pointer; color: white; font-weight: bold; }
        .btn-n { background-color: #28a745; }
        .btn-p { background-color: #007bff; }
    </style>
</head>
<body>
    <h1>Retire sua Senha</h1>
    <button class="btn btn-n" onclick="pedir('normal')">ATENDIMENTO NORMAL</button><br>
    <button class="btn btn-p" onclick="pedir('preferencial')">PREFERENCIAL</button>
    <script>
        var socket = io();
        function pedir(t) { socket.emit('solicitar_senha', {tipo: t}); alert('Senha emitida!'); }
    </script>
</body>
</html>
"""

HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel de Chamadas</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: 'Arial Black', sans-serif; background: #000; color: #fff; }
        .box { border: 10px solid #444; margin: 50px; padding: 40px; border-radius: 30px; }
        h1 { font-size: 60px; color: #ffcc00; }
        #senha { font-size: 200px; color: #00ff00; margin: 20px 0; }
        #tipo { font-size: 50px; color: #aaa; }
    </style>
</head>
<body>
    <div class="box">
        <h1>SENHA ATUAL</h1>
        <div id="senha">---</div>
        <div id="tipo">AGUARDANDO...</div>
    </div>
    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo.toUpperCase();
            var msg = new SpeechSynthesisUtterance("Senha " + data.senha);
            window.speechSynthesis.speak(msg);
        });
    </script>
</body>
</html>
"""

HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: sans-serif; padding: 30px; line-height: 1.6; }
        button { font-size: 22px; padding: 20px; background: #dc3545; color: white; border: none; border-radius: 8px; cursor: pointer; width: 100%; }
        .status { background: #e9ecef; padding: 20px; border-radius: 8px; margin-top: 20px; }
    </style>
</head>
<body>
    <h2>Controle de Chamadas</h2>
    <button onclick="socket.emit('chamar_proximo')">PRÓXIMA SENHA 📢</button>
    <div class="status">
        <p>Preferencial: <b id="p">0</b> em espera</p>
        <p>Normal: <b id="n">0</b> em espera</p>
    </div>
    <script>
        var socket = io();
        socket.on('atualizar_fila', function(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        });
    </script>
</body>
</html>
"""

# --- ROTAS ---
@app.route('/')
def totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def atendente(): return render_template_string(HTML_ATENDENTE)

# --- LÓGICA WEBSOCKET ---

@socketio.on('solicitar_senha')
def handle_solicitar_senha(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    numero_senha = f"{prefixo}-{contadores[tipo]:03d}"
    contadores[tipo] += 1
    fila[tipo].append(numero_senha)
    imprimir_senha_termica(numero_senha, tipo)
    socketio.emit('atualizar_fila', fila)

@socketio.on('chamar_proximo')
def handle_chamar_proximo():
    senha_chamada = None
    tipo_chamada = ""
    if fila['preferencial']:
        senha_chamada = fila['preferencial'].pop(0)
        tipo_chamada = "Preferencial"
    elif fila['normal']:
        senha_chamada = fila['normal'].pop(0)
        tipo_chamada = "Normal"
    
    if senha_chamada:
        socketio.emit('chamar_painel', {'senha': senha_chamada, 'tipo': tipo_chamada})
        socketio.emit('atualizar_fila', fila)

# --- EXECUÇÃO ---
if __name__ == '__main__':
    import eventlet
    import eventlet.wsgi
    
    # Porta dinâmica para compatibilidade com nuvem ou local
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor rodando na porta {port}")
    
    # Usa o servidor Eventlet diretamente para máxima estabilidade
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app)