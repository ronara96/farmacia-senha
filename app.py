import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'farmacia_secret_2026'
# Configuração estável para o Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- BANCO DE DADOS EM MEMÓRIA ---
fila = {"normal": [], "preferencial": []}
contadores = {"normal": 1, "preferencial": 1}
ultima_senha = {"senha": "---", "tipo": "Aguardando..."}

# --- ESTILOS VISUAIS (Separados para não dar erro 500) ---
CSS_BASE = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
    :root { --primary: #2563eb; --success: #10b981; --dark: #0f172a; }
    body { font-family: 'Inter', sans-serif; margin: 0; background: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
    .container { background: white; padding: 3rem; border-radius: 2rem; box-shadow: 0 20px 25px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 500px; }
    .btn { width: 100%; padding: 1.5rem; margin: 10px 0; border-radius: 1rem; border: none; font-size: 1.6rem; font-weight: 800; cursor: pointer; color: white; transition: 0.2s; }
    .btn-normal { background: var(--success); box-shadow: 0 5px 0 #059669; }
    .btn-pref { background: var(--primary); box-shadow: 0 5px 0 #1d4ed8; }
    .btn:active { transform: translateY(3px); box-shadow: none; }
    .tv-bg { background: var(--dark); color: white; }
    .tv-senha { font-size: 15rem; font-weight: 800; color: var(--success); margin: 0; }
</style>
"""

# --- HTML DAS TELAS ---

@app.route('/')
def r_totem():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head><title>Totem</title>""" + CSS_BASE + """</head>
<body>
    <div class="container">
        <h1 style="font-weight:800; font-size:2.5rem; margin-bottom:0.5rem;">FARMÁCIA</h1>
        <p style="color:#64748b; margin-bottom:2.5rem;">Toque para retirar sua senha</p>
        <button class="btn btn-normal" onclick="gerar('normal')">ATENDIMENTO NORMAL</button>
        <button class="btn btn-pref" onclick="gerar('preferencial')">PREFERENCIAL</button>
    </div>
    <iframe id="print_frame" style="display:none;"></iframe>
    <script>
        async function gerar(tipo) {
            try {
                const res = await fetch('/api/gerar?tipo=' + tipo);
                if (!res.ok) throw new Error('Erro no servidor');
                const data = await res.json();
                
                const frame = document.getElementById('print_frame');
                const doc = frame.contentWindow.document;
                
                const ticket = `
                    <html>
                    <body style="text-align:center; font-family:Arial; padding:20px;">
                        <h2 style="margin:0;">FARMÁCIA</h2>
                        <hr>
                        <p style="font-size:14px;">SENHA DE ATENDIMENTO</p>
                        <h1 style="font-size:60px; margin:10px 0;">${data.senha}</h1>
                        <p style="font-size:18px; font-weight:bold;">${data.tipo_extenso}</p>
                        <hr>
                        <p style="font-size:10px;">${new Date().toLocaleString('pt-BR')}</p>
                    </body>
                    </html>
                `;
                doc.open(); doc.write(ticket); doc.close();
                
                setTimeout(() => {
                    frame.contentWindow.focus();
                    frame.contentWindow.print();
                }, 500);
            } catch (err) {
                alert("Erro ao gerar senha. Tente novamente.");
            }
        }
    </script>
</body>
</html>
""")

@app.route('/painel')
def r_painel():
    return render_template_string("""
<!DOCTYPE html>
<html class="tv-bg"><head><script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>""" + CSS_BASE + """</head>
<body class="tv-bg">
    <button onclick="this.style.display='none'" style="position:fixed; top:20px; right:20px; padding:15px; background:red; color:white; border-radius:10px; border:none;">🔊 ATIVAR SOM</button>
    <div style="text-align:center;">
        <div style="font-size: 2rem; color: #64748b;">SENHA CHAMADA</div>
        <div id="senha" class="tv-senha">---</div>
        <div id="tipo" style="font-size:3rem; color:#38bdf8;">AGUARDANDO...</div>
    </div>
    <script>
        var socket = io(); var ultima = "";
        function att(data) {
            if (data.senha !== "---" && data.senha !== ultima) {
                document.getElementById('senha').innerText = data.senha;
                document.getElementById('tipo').innerText = data.tipo;
                ultima = data.senha;
                var m = new SpeechSynthesisUtterance("Senha " + data.senha + ", " + data.tipo);
                m.lang = 'pt-BR'; window.speechSynthesis.speak(m);
            }
        }
        socket.on('chamar_painel', att);
        setInterval(async () => { try { let r = await fetch('/api/estado'); let d = await r.json(); att(d.senha_atual); } catch(e) {} }, 3000);
    </script>
</body></html>
""")

@app.route('/atendente')
def r_atendente():
    return render_template_string("""
<!DOCTYPE html>
<html><head><script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>""" + CSS_BASE + """</head>
<body>
    <div class="container">
        <h2>Atendimento</h2>
        <div style="display:flex; gap:20px; margin-bottom:2rem;">
            <div style="flex:1; background:#f1f5f9; padding:20px; border-radius:1rem;">NORMAL: <b id="n">0</b></div>
            <div style="flex:1; background:#f1f5f9; padding:20px; border-radius:1rem;">PREF: <b id="p" style="color:#2563eb;">0</b></div>
        </div>
        <button class="btn" style="background:#f59e0b;" onclick="fetch('/api/chamar')">📢 CHAMAR PRÓXIMO</button>
    </div>
    <script>
        var socket = io();
        socket.on('atualizar_fila', d => { document.getElementById('n').innerText = d.normal.length; document.getElementById('p').innerText = d.preferencial.length; });
        setInterval(async () => { try { let r = await fetch('/api/estado'); let d = await r.json(); document.getElementById('n').innerText = d.fila.normal.length; document.getElementById('p').innerText = d.fila.preferencial.length; } catch(e) {} }, 2000);
    </script>
</body></html>
""")

# --- LÓGICA DO SERVIDOR ---

@app.route('/api/estado')
def api_estado():
    return jsonify({"fila": fila, "senha_atual": ultima_senha})

@app.route('/api/gerar')
def api_gerar():
    try:
        t = request.args.get('tipo', 'normal')
        if t not in contadores: t = 'normal'
        
        num = contadores[t]
        prefixo = 'N' if t == 'normal' else 'P'
        s = f"{prefixo}-{num:02d}"
        
        fila[t].append(s)
        tipo_ext = "Normal" if t == 'normal' else "Preferencial"
        
        # Reinicia no 100
        if contadores[t] >= 100:
            contadores[t] = 1
        else:
            contadores[t] += 1
            
        socketio.emit('atualizar_fila', fila)
        return jsonify({"status": "ok", "senha": s, "numero": num, "tipo_extenso": tipo_ext})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chamar')
def api_chamar():
    senha = None; tipo = ""
    if fila['preferencial']:
        senha = fila['preferencial'].pop(0); tipo = "Preferencial"
    elif fila['normal']:
        senha = fila['normal'].pop(0); tipo = "Normal"
    
    if senha:
        ultima_senha['senha'] = senha
        ultima_senha['tipo'] = tipo
        socketio.emit('chamar_painel', ultima_senha)
        socketio.emit('atualizar_fila', fila)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
