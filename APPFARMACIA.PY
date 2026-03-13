from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'senha-secreta'
socketio = SocketIO(app)

# Banco de dados temporário em memória
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}

# ==========================================
# INTEGRAÇÃO COM IMPRESSORA TÉRMICA (MOCK)
# ==========================================
def imprimir_senha_termica(senha, tipo):
    """
    Aqui entrará o código da biblioteca python-escpos.
    Exemplo real futuro:
    from escpos.printer import Usb
    p = Usb(0x04b8, 0x0202, 0, 0x81, 0x03) # IDs da sua impressora
    p.text("CLINICA DE SAUDE\n")
    p.text(f"SENHA: {senha}\n")
    p.text(f"TIPO: {tipo}\n")
    p.cut()
    """
    print(f"\n[IMPRESSORA TÉRMICA] Imprimindo: {senha} ({tipo})\n")


# ==========================================
# ROTAS DAS TELAS (FRONTEND)
# ==========================================

# 1. TELA DO TABLET (TOTEM)
HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Retirar Senha</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { text-align: center; font-family: Arial; padding-top: 50px; }
        button { font-size: 30px; padding: 30px; margin: 20px; cursor: pointer; border-radius: 10px; }
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
            alert('Senha solicitada! Retire seu papel.');
        }
    </script>
</body>
</html>
"""

# 2. TELA DO PAINEL DA TV
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
            // Aqui você pode adicionar um som (Audio em JS)
            document.getElementById('senhaAtual').innerText = data.senha;
            document.getElementById('tipoAtual').innerText = data.tipo.toUpperCase();
        });
    </script>
</body>
</html>
"""

# 3. TELA DO ATENDENTE
HTML_ATENDENTE = """
<!DOCTYPE html>
<html>
<head>
    <title>Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: Arial; padding: 20px; }
        button { font-size: 20px; padding: 15px; background: #f44336; color: white; cursor:pointer;}
    </style>
</head>
<body>
    <h1>Painel do Atendente</h1>
    <button onclick="chamarProximo()">📢 Chamar Próxima Senha</button>
    
    <h3>Fila Atual:</h3>
    <p>Preferencial: <span id="fila-p">0</span> aguardando</p>
    <p>Normal: <span id="fila-n">0</span> aguardando</p>

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


# ==========================================
# LÓGICA DO WEBSOCKET (TEMPO REAL)
# ==========================================

@socketio.on('solicitar_senha')
def handle_solicitar_senha(data):
    tipo = data['tipo']
    prefixo = 'N' if tipo == 'normal' else 'P'
    
    # Gera a senha (ex: N-001)
    numero_senha = f"{prefixo}-{contadores[tipo]:03d}"
    contadores[tipo] += 1
    
    # Adiciona na fila
    fila[tipo].append(numero_senha)
    
    # Chama a função de imprimir
    imprimir_senha_termica(numero_senha, tipo)
    
    # Atualiza a tela do atendente com os novos tamanhos da fila
    socketio.emit('atualizar_fila', fila)

@socketio.on('chamar_proximo')
def handle_chamar_proximo():
    senha_chamada = None
    tipo_chamada = ""

    # Lógica de prioridade: Chama preferencial primeiro, se houver
    if len(fila['preferencial']) > 0:
        senha_chamada = fila['preferencial'].pop(0)
        tipo_chamada = "Preferencial"
    elif len(fila['normal']) > 0:
        senha_chamada = fila['normal'].pop(0)
        tipo_chamada = "Normal"

    if senha_chamada:
        # Manda a TV (Painel) mostrar a senha
        socketio.emit('chamar_painel', {'senha': senha_chamada, 'tipo': tipo_chamada})
        # Atualiza a contagem na tela do atendente
        socketio.emit('atualizar_fila', fila)


if __name__ == '__main__':
    # Roda o servidor na rede local (0.0.0.0 permite acesso pelo tablet/TV via IP)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
