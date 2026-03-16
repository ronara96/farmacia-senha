import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sigaf_farmacia_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- BANCO DE DADOS TEMPORÁRIO ---
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha = {"senha": "---", "tipo": "Aguardando..."}

# --- ESTILO CSS PROFISSIONAL ---
CSS_MODERNO = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
    :root {
        --primary: #2563eb; --secondary: #64748b; --success: #10b981;
        --danger: #ef4444; --warning: #f59e0b; --dark: #0f172a;
    }
    body { 
        font-family: 'Inter', sans-serif; margin: 0; background: #f8fafc; 
        color: #1e293b; display: flex; align-items: center; justify-content: center; height: 100vh;
        overflow: hidden;
    }
    .container { 
        background: white; padding: 3rem; border-radius: 2rem; 
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 500px;
    }
    .btn {
        width: 100%; padding: 1.5rem; margin: 10px 0; border-radius: 1rem; border: none;
        font-size: 1.5rem; font-weight: 700; cursor: pointer; transition: 0.2s; color: white;
    }
    .btn:active { transform: scale(0.98); }
    .btn-normal { background: var(--success); box-shadow: 0 4px 0 #059669; }
    .btn-pref { background: var(--primary); box-shadow: 0 4px 0 #1d4ed8; }
    .btn-call { background: var(--warning); box-shadow: 0 4px 0 #d97706; font-size: 1.5rem; }
    
    /* Painel TV */
    .tv-bg { background: var(--dark); color: white; }
    .tv-card { background: #1e293b; border: 1px solid #334155; padding: 4rem; border-radius: 3rem; width: 80%; }
    .tv-senha { font-size: 15rem; font-weight: 800; color: var(--success); margin: 0; line-height: 1; }
    .tv-tipo { font-size: 3rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 4px; }
</style>
"""

# --- TEMPLATES HTML ---

HTML_TOTEM = """
<!DOCTYPE html>
<html>
<head>
    <title>Totem de Senhas</title>
    {{ css|safe }}
</head>
<body>
    <div class="container">
        <h1 style="font-weight:800; font-size:2rem; margin-bottom:0.5rem;">FARMÁCIA</h1>
        <p style="color:var(--secondary); margin-bottom:2.5rem;">Toque no botão para gerar sua senha</p>
        <button class="btn btn-normal" onclick="gerarSenha('normal')">ATENDIMENTO NORMAL</button>
        <button class="btn btn-pref" onclick="gerarSenha('preferencial')">PREFERENCIAL</button>
    </div>

    <script>
        async function gerarSenha(tipo) {
            try {
                const res = await fetch('/api/gerar?tipo=' + tipo);
                const data = await res.json();
                
                // Conteúdo para a mini-janela de impressão
                const ticket = `
                    <html>
                    <body style="text-align:center; font-family:sans-serif; padding:10px;">
                        <h2 style="margin:0;">FARMÁCIA</h2>
                        <hr>
                        <p style="font-size:12px; margin:5px 0;">SENHA DE ATENDIMENTO</p>
                        <h1 style="font-size:60px; margin:10px 0;">${data.senha}</h1>
                        <p style="font-size:16px; font-weight:bold;">${data.tipo_extenso}</p>
                        <hr>
                        <p style="font-size:10px;">${new Date().toLocaleString('pt-BR')}</p>
                    </body>
                    <script>window.print(); setTimeout(() => window.close(), 500);<\\/script>
                    </html>
                `;

                // Abre a janelinha de impressão
                const winPrint = window.open('', '', 'width=300,height=450');
                winPrint.document.write(ticket);
                winPrint.document.close();

                // Alerta para o paciente/idoso
                alert('SUA SENHA É: ' + data.senha + '\\n\\nPegue seu ticket ou a ficha física número ' + data.numero);
            } catch (err) {
                alert("Erro ao gerar senha. Verifique a conexão.");
            }
        }
    </script>
</body>
</html>
"""

HTML_PAINEL = """
<!DOCTYPE html>
<html class="tv-bg">
<head>
    <title>Painel TV</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    {{ css|safe }}
</head>
<body class="tv-bg">
    <button onclick="this.style.display='none'" style="position:fixed; top:20px; right:20px; padding:15px; background:var(--danger); color:white; border-radius:10px; border:none; cursor:pointer;">🔊 ATIVAR SOM</button>
    <div class="tv-card text-center">
        <div style="font-size: 2rem; color: var(--secondary);">SENHA CHAMADA</div>
        <div id="senha" class="tv-senha">---</div>
        <div id="tipo" class="tv-tipo">AGUARDANDO</div>
    </div>
    <script>
        var socket = io();
        var ultimaLida = "";
        function atualizarTela(data) {
            if (data.senha !== "---" && data.senha !== ultimaLida) {
                document.getElementById('senha').innerText = data.senha;
                document.getElementById('tipo').innerText = data.tipo;
                ultimaLida = data.senha;
                var msg = new SpeechSynthesisUtterance("Senha " + data.senha + ", " + data.tipo);
                msg.lang = 'pt-BR';
                window.speechSynthesis.speak(msg);
            }
        }
        socket.on('chamar_painel', atualizarTela);
        setInterval(async () => {
            try { let res = await fetch('/api/estado'); let data = await res.json(); atualizarTela(data.senha_atual); } catch(e) {}
        }, 3000);
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
    {{ css|safe }}
</head>
<body>
    <div class="container">
        <h2 style="margin-bottom: 2rem;">Controle de Fila</h2>
        <div style="display:flex; gap:20px; margin-bottom: 2rem;">
            <div style="flex:1; background:#f1f5f9; padding:20px; border-radius:1rem;">
                <small>NORMAL</small>
                <div id="n" style="font-size:2.5rem; font-weight:800;">0</div>
            </div>
            <div style="flex:1; background:#f1f5f9; padding:20px; border-radius:1rem;">
                <small>PREFERENCIAL</small>
                <div id="p" style="font-size:2.5rem; font-weight:800; color:var(--primary);">0</div>
            </div>
        </div>
        <button class="btn btn-call" onclick="fetch('/api/chamar')">📢 CHAMAR PRÓXIMO</button>
    </div>
    <script>
        var socket = io();
        function atualizarFila(data) {
            document.getElementById('p').innerText = data.preferencial.length;
            document.getElementById('n').innerText = data.normal.length;
        }
        socket.on('atualizar_fila', atualizarFila);
        setInterval(async () => {
            try { let res = await fetch('/api/estado'); let data = await res.json(); atualizarFila(data.fila); } catch(e) {}
        }, 2000);
    </script>
</body>
</html>
"""

# --- ROTAS ---

@app.route('/')
def r_totem():
    return render_template_string(HTML_TOTEM, css=CSS_MODERNO)

@app.route('/painel')
def r_painel():
    return render_template_string(HTML_PAINEL, css=CSS_MODERNO)

@app.route('/atendente')
def r_atendente():
    return render_template_string(HTML_ATENDENTE, css=CSS_MODERNO)

@app.route('/api/estado')
def api_estado():
    return jsonify({"fila": fila, "senha_atual": ultima_senha})

@app.route('/api/gerar')
def api_gerar():
    t = request.args.get('tipo', 'normal')
    num = contadores[t]
    prefixo = 'N' if t == 'normal' else 'P'
    s = f"{prefixo}-{num:02d}"
    fila[t].append(s)
    
    tipo_txt = "Atendimento Normal" if t == 'normal' else "Atendimento Preferencial"
    
    # Reinicia no 100
    if contadores[t] >= 100: contadores[t] = 1
    else: contadores[t] += 1
        
    socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "ok", "senha": s, "numero": num, "tipo_extenso": tipo_txt})

@app.route('/api/chamar')
def api_chamar():
    senha = None
    tipo = ""
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0); tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0); tipo = "Normal"
    
    if senha:
        ultima_senha['senha'] = senha
        ultima_senha['tipo'] = tipo
        socketio.emit('chamar_painel', ultima_senha, broadcast=True)
        socketio.emit('atualizar_fila', fila, broadcast=True)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
