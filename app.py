import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-moderno-2026'
# Timeout aumentado para evitar quedas no Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60)

# --- BANCO DE DADOS EM MEMÓRIA ---
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
senha_atual = {"senha": "---", "tipo": "Aguardando"}

# ==========================================
# 🎨 INTERFACES (HTML + CSS Moderno)
# ==========================================

# 1. TELA DA TV (PAINEL)
HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Painel Sigaf</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap');
        body { margin: 0; background: #0f172a; color: white; font-family: 'Poppins', sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .card { background: #1e293b; padding: 60px 100px; border-radius: 30px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); text-align: center; border: 2px solid #334155; }
        h1 { margin: 0; font-size: 50px; color: #94a3b8; text-transform: uppercase; letter-spacing: 5px; }
        #senha { font-size: 200px; font-weight: 700; color: #10b981; margin: 20px 0; line-height: 1; text-shadow: 0 0 40px rgba(16, 185, 129, 0.4); }
        #tipo { font-size: 50px; color: #38bdf8; font-weight: bold; text-transform: uppercase; }
        .btn-som { position: absolute; top: 20px; right: 20px; padding: 15px 25px; background: #ef4444; color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <button class="btn-som" onclick="this.style.display='none'">🔊 ATIVAR SOM</button>
    <div class="card">
        <h1>Senha Chamada</h1>
        <div id="senha">---</div>
        <div id="tipo">AGUARDANDO</div>
    </div>

    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo;
            
            // Sistema de voz nativo e seguro
            try {
                let voz = new SpeechSynthesisUtterance("Senha " + data.senha + ". " + data.tipo);
                voz.lang = 'pt-BR';
                voz.rate = 0.9;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(voz);
            } catch(e) { console.error("Erro ao reproduzir voz", e); }
        });
    </script>
</body>
</html>
"""

# 2. TELA DO TOTEM (CLIENTE)
HTML_TOTEM = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Retirar Senha</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap');
        body { margin: 0; background: #f8fafc; font-family: 'Poppins', sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }
        h1 { color: #334155; font-size: 40px; margin-bottom: 40px; }
        .btn { width: 80%; max-width: 500px; padding: 40px; margin: 15px; font-size: 35px; font-weight: bold; color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); transition: transform 0.2s, filter 0.2s; }
        .btn:active { transform: scale(0.95); }
        .btn-normal { background: linear-gradient(135deg, #10b981, #059669); }
        .btn-pref { background: linear-gradient(135deg, #3b82f6, #2563eb); }
    </style>
</head>
<body>
    <h1>Selecione seu Atendimento</h1>
    <button class="btn btn-normal" onclick="gerar('normal')">NORMAL</button>
    <button class="btn btn-pref" onclick="gerar('preferencial')">PREFERENCIAL</button>

    <script>
        // Usando a API robusta (HTTP POST) em vez de WebSocket para garantir o clique
        async function gerar(tipo) {
            try {
                await fetch('/api/gerar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tipo: tipo})
                });
                alert('Sua senha foi gerada com sucesso! Aguarde ser chamado.');
            } catch (error) {
                alert('Erro de conexão. Tente novamente.');
            }
        }
    </script>
</body>
</html>
"""

# 3. TELA DO ATENDENTE (BOTÃO QUE NÃO FALHA)
HTML_ATENDENTE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Painel do Atendente</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
        body { background: #e2e8f0; font-family: 'Poppins', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .dashboard { background: white; padding: 40px; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center; width: 100%; max-width: 500px; }
        h2 { color: #475569; margin-top: 0; font-size: 28px; }
        .stats { display: flex; justify-content: space-around; margin: 30px 0; padding: 20px; background: #f8fafc; border-radius: 16px; border: 1px solid #e2e8f0; }
        .stat-box { display: flex; flex-direction: column; }
        .stat-title { font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase; }
        .stat-value { font-size: 48px; font-weight: 700; color: #f97316; line-height: 1; margin-top: 5px; }
        .btn-chamar { width: 100%; padding: 25px; background: linear-gradient(135deg, #f97316, #ea580c); color: white; font-size: 24px; font-weight: bold; border: none; border-radius: 16px; cursor: pointer; box-shadow: 0 10px 15px -3px rgba(249, 115, 22, 0.4); transition: transform 0.1s; }
        .btn-chamar:active { transform: translateY(4px); box-shadow: 0 4px 6px -1px rgba(249, 115, 22, 0.4); }
        .btn-chamar:disabled { background: #cbd5e1; cursor: not-allowed; box-shadow: none; transform: none; }
    </style>
</head>
<body>
    <div class="dashboard">
        <h2>Controle de Fila</h2>
        
        <div class="stats">
            <div class="stat-box">
                <span class="stat-title">Preferencial</span>
                <span class="stat-value" id="count-p">0</span>
            </div>
            <div class="stat-box">
                <span class="stat-title">Normal</span>
                <span class="stat-value" id="count-n">0</span>
            </div>
        </div>

        <button id="btn-chamar" class="btn-chamar" onclick="chamar()">📢 CHAMAR PRÓXIMO</button>
    </div>

    <script>
        var socket = io();

        // O SEGREDO AQUI: O botão usa HTTP (Fetch) para garantir que a ordem chegue no servidor.
        async function chamar() {
            let btn = document.getElementById('btn-chamar');
            btn.disabled = true; // Impede duplo clique rápido
            btn.innerText = "CHAMANDO...";
            
            try {
                await fetch('/api/chamar', { method: 'POST' });
            } catch (e) {
                console.error("Erro na requisição:", e);
                alert("Erro ao chamar. Verifique a internet.");
            }
            
            setTimeout(() => { 
                btn.disabled = false; 
                btn.innerText = "📢 CHAMAR PRÓXIMO";
            }, 1000);
        }

        // O Socket fica APENAS escutando atualizações para mudar os números na tela
        socket.on('atualizar_fila', function(data) {
            document.getElementById('count-p').innerText = data.preferencial.length;
            document.getElementById('count-n').innerText = data.normal.length;
        });

        // Quando a página carrega, pede os números atuais
        window.onload = async function() {
            let res = await fetch('/api/estado');
            let data = await res.json();
            document.getElementById('count-p').innerText = data.fila.preferencial.length;
            document.getElementById('count-n').innerText = data.fila.normal.length;
        };
    </script>
</body>
</html>
"""

# ==========================================
# ⚙️ ROTAS E APIS DO SERVIDOR
# ==========================================

@app.route('/')
def rota_totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def rota_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def rota_atendente(): return render_template_string(HTML_ATENDENTE)

# API: Retorna o estado atual (Usado ao abrir a tela)
@app.route('/api/estado', methods=['GET'])
def api_estado():
    return jsonify({"fila": fila, "senha_atual": senha_atual})

# API: Gerar nova senha (Garantido pelo botão do Totem)
@app.route('/api/gerar', methods=['POST'])
def api_gerar():
    dados = request.json
    tipo = dados.get('tipo', 'normal')
    prefixo = 'N' if tipo == 'normal' else 'P'
    senha = f"{prefixo}-{contadores[tipo]:03d}"
    
    contadores[tipo] += 1
    fila[tipo].append(senha)
    
    # Avisa as telas que a fila cresceu
    socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "sucesso", "senha": senha})

# API: Chamar próxima senha (GARANTIDO PELO BOTÃO DO ATENDENTE)
@app.route('/api/chamar', methods=['POST'])
def api_chamar():
    senha = None
    tipo = ""
    
    # Lógica de prioridade
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
        tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0)
        tipo = "Normal"
    
    if senha:
        senha_atual['senha'] = senha
        senha_atual['tipo'] = tipo
        
        # Avisa a TV para mostrar e falar a senha
        socketio.emit('chamar_painel', senha_atual, broadcast=True)
        # Avisa os atendentes para diminuir o número da tela
        socketio.emit('atualizar_fila', fila, broadcast=True)
        
        return jsonify({"status": "sucesso", "chamado": senha})
    
    return jsonify({"status": "vazio", "mensagem": "Ninguém na fila"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
