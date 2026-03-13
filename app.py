import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'senha-secreta'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados temporário
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha_gerada = {"senha": "", "tipo": ""}

@app.route('/')
def totem():
    return render_template_string(HTML_TOTEM)

@app.route('/painel')
def painel():
    return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def atendente():
    return render_template_string(HTML_ATENDENTE)

# Rota para o seu PC local consultar se há algo para imprimir
@app.route('/imprimir/status')
def status_impressao():
    return jsonify(ultima_senha_gerada)

@socketio.on('solicitar_senha')
def handle_solicitar_senha(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    numero_senha = f"{prefixo}-{contadores[tipo]:03d}"
    
    contadores[tipo] += 1
    fila[tipo].append(numero_senha)
    
    # Atualiza para o script local imprimir
    ultima_senha_gerada['senha'] = numero_senha
    ultima_senha_gerada['tipo'] = tipo
    
    socketio.emit('atualizar_fila', fila)
    print(f"Senha Gerada: {numero_senha}")

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
        socketio.emit('chamar_painel', {'senha': senha_chamada, 'tipo': tipo_chamada})
        socketio.emit('atualizar_fila', fila)

# --- TELAS HTML (COM CORREÇÃO DE SOM) ---

HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem Zebra</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: sans-serif; background: #f0f0f0; }
        button { font-size: 40px; width: 80%; padding: 50px; margin: 20px; cursor: pointer; border: none; border-radius: 20px; color: white; font-weight: bold; }
        .btn-n { background: #2ecc71; }
        .btn-p { background: #3498db; }
    </style>
</head>
<body>
    <h1>Toque para retirar sua senha:</h1>
    <button class="btn-n" onclick="pedir('normal')">ATENDIMENTO NORMAL</button>
    <button class="btn-p" onclick="pedir('preferencial')">PREFERENCIAL</button>
    <script>
        var socket = io();
        function pedir(t) { socket.emit('solicitar_senha', {tipo: t}); alert('Imprimindo senha...'); }
    </script>
</body>
</html>
"""

HTML_PAINEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Painel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #fff; text-align: center; font-family: 'Arial Black'; overflow: hidden; }
        #senha { font-size: 250px; color: #00ff00; margin: 0; }
        #info { font-size: 80px; color: #fff; }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body onclick="iniciarAudio()">
    <div id="aviso" style="background:red; padding:10px;">CLIQUE NA TELA PARA ATIVAR O SOM</div>
    <p id="info">SENHA</p>
    <h1 id="senha">---</h1>
    <h2 id="tipo" style="font-size: 50px;">Aguardando...</h2>

    <script>
        var socket = io();
        function iniciarAudio() { document.getElementById('aviso').style.display = 'none'; }

        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo.toUpperCase();
            document.getElementById('senha').classList.add('blink');
            setTimeout(() => { document.getElementById('senha').classList.remove('blink'); }, 5000);

            // VOZ EM PORTUGUÊS
            var msg = new SpeechSynthesisUtterance("Senha " + data.senha + ". " + data.tipo);
            msg.lang = 'pt-BR';
            msg.rate = 0.9;
            window.speechSynthesis.cancel();
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
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body>
    <h1>Controle</h1>
    <button style="padding:40px; font-size:30px; background:orange;" onclick="socket.emit('chamar_proximo')">PRÓXIMO</button>
    <div id="filas"></div>
    <script>
        var socket = io();
        socket.on('atualizar_fila', (f) => {
            document.getElementById('filas').innerHTML = `<p>Normal: ${f.normal.length} | Pref: ${f.preferencial.length}</p>`;
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
