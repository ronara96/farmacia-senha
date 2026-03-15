import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf-moderno-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- BANCO DE DADOS EM MEMÓRIA ---
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
senha_atual = {"senha": "---", "tipo": "Aguardando"}

# ==========================================
# 🎨 TELA DA TV (PAINEL)
# ==========================================
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
        .btn-som { position: absolute; top: 20px; right: 20px; padding: 15px 25px; background: #ef4444; color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <button class="btn-som" onclick="this.style.display='none'">🔊 ATIVAR SOM DA TV</button>
    <div class="card">
        <h1>Senha Chamada</h1>
        <div id="senha">---</div>
        <div id="tipo">AGUARDANDO</div>
    </div>

    <script>
        var socket = io();
        socket.on('chamar_painel', function(data) {
            console.log("NOVA SENHA RECEBIDA:", data);
            document.getElementById('senha').innerText = data.senha;
            document.getElementById('tipo').innerText = data.tipo;
            
            try {
                let voz = new SpeechSynthesisUtterance("Senha " + data.senha + ". " + data.tipo);
                voz.lang = 'pt-BR';
                voz.rate = 0.9;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(voz);
            } catch(e) { console.error("Erro na voz", e); }
        });
    </script>
</body>
</html>
"""

# ==========================================
# 🎨 TELA DO TOTEM (CLIENTE)
# ==========================================
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
        .btn { width: 80%; max-width: 500px; padding: 40px; margin: 15px; font-size: 35px; font-weight: bold; color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
        .btn-normal { background: linear-gradient(135deg, #10b981, #059669); }
        .btn-pref { background: linear-gradient(135deg, #3b82f6, #2563eb); }
    </style>
</head>
<body>
    <h1>Selecione seu Atendimento</h1>
    <button class="btn btn-normal" onclick="gerar('normal')">NORMAL</button>
    <button class="btn btn-pref" onclick="gerar('preferencial')">PREFERENCIAL</button>

    <script>
        async function gerar(tipo) {
            // Usa GET para não ser bloqueado
            let url = '/api/gerar?tipo=' + tipo + '&t=' + new Date().getTime();
            await fetch(url);
            alert('Sua senha foi gerada com sucesso! Aguarde ser chamado.');
        }
    </script>
</body>
</html>
"""

# ==========================================
# 🎨 TELA DO ATENDENTE (BOTÃO QUE NÃO FALHA)
# ==========================================
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
        .stat-value { font-size: 48px; font-weight: 700; color: #f97316; margin-top: 5px; }
        .btn-chamar { width: 100%; padding: 25px; background: linear-gradient(135deg, #f97316, #ea580c); color: white; font-size: 24px; font-weight: bold; border: none; border-radius: 16px; cursor: pointer; }
        .btn-chamar:disabled { background: #cbd5e1; cursor: not-allowed; }
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

        async function chamar() {
            let btn = document.getElementById('btn-chamar');
            btn.disabled = true; 
            btn.innerText = "CHAMANDO...";
            
            try {
                // MUDANÇA CRÍTICA: GET com relógio (anti-bloqueio)
                let url = '/api/chamar?t=' + new Date().getTime();
                await fetch(url);
            } catch (e) {
                console.error("Erro na requisição:", e);
            }
            
            setTimeout(() => { 
                btn.disabled = false; 
                btn.innerText = "📢 CHAMAR PRÓXIMO";
            }, 1000);
        }

        socket.on('atualizar_fila', function(data) {
            document.getElementById('count-p').innerText = data.preferencial.length;
            document.getElementById('count-n').innerText = data.normal.length;
        });

        window.onload = async function() {
            let res = await fetch('/api/estado?t=' + new Date().getTime());
            let data = await res.json();
            document.getElementById('count-p').innerText = data.fila.preferencial.length;
            document.getElementById('count-n').innerText = data.fila.normal.length;
        };
    </script>
</body>
</html>
"""

# ==========================================
# ⚙️ ROTAS DO SERVIDOR
# ==========================================

@app.route('/')
def rota_totem(): return render_template_string(HTML_TOTEM)

@app.route('/painel')
def rota_painel(): return render_template_string(HTML_PAINEL)

@app.route('/atendente')
def rota_atendente(): return render_template_string(HTML_ATENDENTE)

@app.route('/api/estado', methods=['GET'])
def api_estado():
    return jsonify({"fila": fila})

@app.route('/api/gerar', methods=['GET'])
def api_gerar():
    tipo = request.args.get('tipo', 'normal')
    prefixo = 'N' if tipo == 'normal' else 'P'
    senha = f"{prefixo}-{contadores[tipo]:03d}"
    
    contadores[tipo] += 1
    fila[tipo].append(senha)
    
    print(f"✅ GEROU SENHA: {senha} - Fila atualizada!")
    socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "sucesso"})

# A ROTA BLINDADA DO BOTÃO (Mudou para GET)
@app.route('/api/chamar', methods=['GET'])
def api_chamar():
    print("🚀 O BOTAO DE CHAMAR FOI CLICADO E O SINAL CHEGOU NO SERVIDOR!")
    
    senha = None
    tipo = ""
    
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0)
        tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0)
        tipo = "Normal"
    
    if senha:
        senha_atual['senha'] = senha
        senha_atual['tipo'] = tipo
        
        print(f"📺 ENVIANDO PARA A TV: {senha}")
        socketio.emit('chamar_painel', senha_atual, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)
        
        return jsonify({"status": "sucesso", "chamado": senha})
    
    print("⚠️ BOTAO APERTADO, MAS A FILA ESTAVA VAZIA!")
    return jsonify({"status": "vazio"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
