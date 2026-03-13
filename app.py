# 1. ESTAS LINHAS DEVEM SER AS PRIMEIRAS DO ARQUIVO
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO

# 2. CONFIGURAÇÃO DO APP
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!' # Você pode mudar para uma senha sua
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 3. SUAS ROTAS (EXEMPLO)
@app.route('/')
def index():
    # Certifique-se de que seus arquivos HTML estão na pasta 'templates'
    return "Painel da Farmácia Rodando com Sucesso!"

# 4. EVENTOS DO SOCKET (EXEMPLO DE CHAMADA)
@socketio.on('proxima_senha')
def handle_senha(data):
    print(f"Chamando senha: {data}")
    socketio.emit('exibir_senha', data, broadcast=True)

# 5. EXECUÇÃO (IMPORTANTE PARA LOCAL E RENDER)
if __name__ == '__main__':
    # O Render usa o Gunicorn, então isso aqui roda mais no seu PC
    socketio.run(app, debug=True)
