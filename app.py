import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zebra-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Banco de dados em memória
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
# Fila para a impressora física buscar
pendentes_impressao = []

# --- HTML PAINEL (COM SOM CORRIGIDO) ---
HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Painel de Chamadas</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #1a1a1a; color: white; font-family: sans-serif; text-align: center; padding: 50px; }
        #box { border: 10px solid #444; border-radius: 30px; padding: 40px; background: #000; }
        #senha { font-size: 200px; color: #00ff00; margin: 20px 0; }
        #tipo { font-size: 60px; color: #3498db; }
        #btn-som { padding: 20px; background: #e74c3c; color: white; border: none; cursor: pointer; border-radius: 10px; font-size: 20px; }
    </style>
</head>
<body>
    <button id="btn-som" onclick="this.style.display='none'">🔊 CLIQUE PARA ATIVAR O SOM</button>
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

# --- HTML TOTEM ---
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; padding-top: 50px; }
        button { font-size: 40px; padding: 50px; margin: 20px; width: 80%; cursor: pointer; border-radius: 20px; border: none; color: white; }
        .btn-n { background: #27ae60; }
        .btn-p { background: #2980b9; }
    </style>
</head>
<body>
    <h1>Selecione o Atendimento</h1>
    <button class="btn-n" onclick="socket.emit('solicitar_senha', {tipo: 'normal'})">NORMAL</button>
    <button class="btn-p" onclick="socket.emit('solicitar_senha', {tipo: 'preferencial'})">PREFERENCIAL</button>
    <script>var socket = io(); socket.on('atualizar_fila', function() { alert('Senha Gerada! Retire no papel.'); });</script>
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

@app.route('/api/get_print')
def get_print():
    if pendentes_impressao:
        return jsonify(pendentes_impressao.pop(0))
    return jsonify({"status": "vazio"}), 200

@socketio.on('solicitar_senha')
def handle_solicitar_senha(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    numero = f"{prefixo}-{contadores[tipo]:03d}"
    contadores[tipo] += 1
    fila[tipo].append(numero)
    pendentes_impressao.append({"senha": numero, "tipo": tipo.upper()})
    socketio.emit('atualizar_fila', fila)

@socketio.on('chamar_proximo')
def handle_chamar_proximo():
    s = None
    t = ""
    if fila['preferencial']:
        s = fila['preferencial'].pop(0)
        t = "Preferencial"
    elif fila['normal']:
        s = fila['normal'].pop(0)
        t = "Normal"
    if s:
        socketio.emit('chamar_painel', {'senha': s, 'tipo': t}, broadcast=True)

HTML_ATENDENTE = """<button onclick="socket.emit('chamar_proximo')">PRÓXIMO</button><script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script><script>var socket = io();</script>"""

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
