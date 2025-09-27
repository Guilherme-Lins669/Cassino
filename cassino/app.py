# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import random
import os

from extensions import db  # vem do arquivo extensions.py


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'troque-por-uma-chave-secreta')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cassino.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        import models
        db.create_all()

    return app


app = create_app()


# Helpers
def ensure_logged():
    return 'player_id' in session


# ---------- ROTAS ----------
@app.route('/')
def index():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    from models import Player

    name = request.form['name'].strip()
    if not name:
        return redirect(url_for('index'))

    player = Player.query.filter_by(name=name).first()

    if not player:
        player = Player(name=name, balance=0, initial_deposit=0)
        db.session.add(player)
        db.session.commit()
        session['first_time'] = True
    else:
        if player.initial_deposit == 0 and player.balance == 0:
            session['first_time'] = True
        else:
            session['first_time'] = False

    session['player_id'] = player.id
    # Novo fluxo: após criar/entrar na conta, redireciona direto para o lobby (saldo pode ser 0)
    return redirect(url_for('lobby'))


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    from models import Player

    if "player_id" not in session:
        return redirect(url_for("index"))

    player = Player.query.get(session["player_id"])

    # Permitir POST via JSON (AJAX) ou form tradicional
    if request.method == "POST":
        # obter valor do JSON ou do form
        if request.is_json:
            data = request.get_json()
            amount_raw = data.get("amount")
        else:
            amount_raw = request.form.get("amount")

        try:
            valor = float(amount_raw)
        except (ValueError, TypeError):
            # Se for AJAX, retornar JSON com erro; se não, renderizar template
            if request.is_json:
                return jsonify({"error": "Valor inválido"}), 400
            return render_template("deposit.html", player=player, error="Valor inválido")

        # novo mínimo inicial: R$ 50
        if valor < 50 and player.initial_deposit == 0:
            if request.is_json:
                return jsonify({"error": "O depósito mínimo inicial é R$ 50"}), 400
            return render_template("deposit.html", player=player, error="O depósito mínimo inicial é R$ 50")

        # atualizar saldo
        if player.initial_deposit == 0:
            player.initial_deposit = float(valor)
            player.balance = float(valor)
        else:
            player.balance = float(player.balance) + float(valor)

        db.session.commit()
        session['first_time'] = False

        if request.is_json:
            return jsonify({"message": "Depósito realizado", "balance": float(player.balance)})
        return redirect(url_for("lobby"))

    # GET: renderiza a página de depósito (ainda disponível se alguém acessar diretamente)
    return render_template("deposit.html", player=player)


@app.route('/lobby')
def lobby():
    if not ensure_logged():
        return redirect(url_for('index'))
    from models import Player
    player = Player.query.get(session['player_id'])
    return render_template('lobby.html', username=player.name, saldo=float(player.balance))


@app.route('/game/<game_name>')
def game(game_name):
    if not ensure_logged():
        return redirect(url_for('index'))
    from models import Player
    player = Player.query.get(session['player_id'])
    saldo = float(player.balance)

    templates = {
        'foguete': 'game_rocket.html',
        'campo_minado': 'game_minesweeper.html',
        'caca_niqueis': 'game_slots.html',
        'roleta': 'game_roulette.html',
        'dados': 'game_dice.html'
    }
    template = templates.get(game_name)
    if not template:
        return redirect(url_for('lobby'))
    return render_template(template, saldo=saldo)


# ------------ CAMPO MINADO ------------
@app.route("/minesweeper/start", methods=["POST"])
def start_minesweeper():
    '''Inicia um novo tabuleiro de Campo Minado'''
    from models import Player

    if not ensure_logged():
        return jsonify({"error": "not logged"}), 403

    player = Player.query.get(session["player_id"])
    data = request.get_json()
    bet = float(data.get("bet", 0))

    if bet <= 0 or bet > float(player.balance):
        return jsonify({"error": "invalid bet"}), 400

    # Configuração do jogo
    size = 5
    bombs = 5
    grid = [[0 for _ in range(size)] for _ in range(size)]

    bomb_positions = random.sample([(r, c) for r in range(size) for c in range(size)], bombs)
    for r, c in bomb_positions:
        grid[r][c] = "B"

    # Armazena na sessão
    session["minesweeper"] = {
        "grid": grid,
        "revealed": [[False for _ in range(size)] for _ in range(size)],
        "bet": bet,
        "active": True
    }

    return jsonify({"message": "Jogo iniciado", "size": size, "bet": bet})


@app.route("/minesweeper/click/<int:row>/<int:col>", methods=["POST"])
def click_minesweeper(row, col):
    '''Processa clique em uma célula do Campo Minado'''
    from models import Player, Match

    if not ensure_logged():
        return jsonify({"error": "not logged"}), 403

    state = session.get("minesweeper")
    if not state or not state.get("active"):
        return jsonify({"error": "no active game"}), 400

    grid = state["grid"]
    revealed = state["revealed"]
    bet = state["bet"]

    from models import Player
    player = Player.query.get(session["player_id"])

    if revealed[row][col]:
        return jsonify({"error": "cell already revealed"}), 400

    revealed[row][col] = True

    if grid[row][col] == "B":
        # Perdeu
        player.balance = float(player.balance) - bet
        db.session.commit()

        match = Match(player_id=player.id, game="campo_minado", bet=bet, payout=-bet,
                      balance_after=float(player.balance), played_at=datetime.utcnow())
        db.session.add(match)
        db.session.commit()

        state["active"] = False
        session["minesweeper"] = state
        return jsonify({"result": "lost", "saldo": float(player.balance)})

    else:
        # Ganhou parcial
        payout = bet * 0.2
        player.balance = float(player.balance) + payout
        db.session.commit()

        match = Match(player_id=player.id, game="campo_minado", bet=bet, payout=payout,
                      balance_after=float(player.balance), played_at=datetime.utcnow())
        db.session.add(match)
        db.session.commit()

        session["minesweeper"] = state
        return jsonify({"result": "safe", "payout": payout, "saldo": float(player.balance)})


# ------------ OUTROS JOGOS ------------
@app.route('/play/<game>', methods=['POST'])
def play(game):
    if not ensure_logged():
        return jsonify({'error': 'not logged'}), 403

    from models import Player, Match
    player = Player.query.get(session['player_id'])

    data = request.get_json() if request.is_json else request.form.to_dict()

    try:
        bet = float(data.get('bet', 0))
    except:
        return jsonify({'error': 'invalid bet'}), 400

    if bet <= 0:
        return jsonify({'error': 'invalid bet'}), 400
    if bet > float(player.balance):
        return jsonify({'error': 'insufficient balance'}), 400

    result = {
        'win': False,
        'payout': 0.0,
        'new_balance': float(player.balance),
        'saldo': float(player.balance),
        'resultado': '',
        'bet': bet,
        'duration': 0
    }

    if game in ['rocket', 'foguete']:
        multiplier = 0.25
        predict = data.get('predict')
        outcome = random.choice(['up', 'down'])
        if predict == outcome:
            payout = bet * multiplier
            player.balance = float(player.balance) + payout
            result.update({'win': True, 'payout': payout, 'resultado': 'Você ganhou!'})
        else:
            player.balance = float(player.balance) - bet
            result.update({'payout': -bet, 'resultado': 'Você perdeu.'})

    elif game in ['slots', 'caca_niqueis']:
        symbols = ["🍒", "🍋", "🍇", "🍉", "⭐", "🔔"]
        reels = [random.choice(symbols) for _ in range(3)]

        if reels[0] == reels[1] == reels[2]:
            payout = bet * 5.0  # pode aumentar o multiplicador se quiser
            player.balance = float(player.balance) + payout
            result.update({'win': True, 'payout': payout, 'resultado': '🎉 Jackpot! Triple!'})
        else:
            player.balance = float(player.balance) - bet
            result.update({'payout': -bet, 'resultado': 'Você perdeu.'})
        result['reels'] = reels

    elif game in ['roulette', 'roleta']:
        multiplier = 3.0
        pick = data.get('pick')
        if random.random() < 0.15:
            payout = bet * multiplier
            player.balance = float(player.balance) + payout
            result.update({'win': True, 'payout': payout, 'resultado': f'Você ganhou na cor {pick}!'})
        else:
            player.balance = float(player.balance) - bet
            result.update({'payout': -bet, 'resultado': f'Você perdeu na cor {pick}.'})

    elif game in ['dice', 'dados']:
        multiplier = 5.0
        try:
            guess = int(data.get('guess'))
        except:
            return jsonify({'error': 'invalid guess'}), 400

        dice = [random.randint(1, 6) for _ in range(5)]
        total = sum(dice)
        result['dice'] = dice
        result['total'] = total  # incluir total no JSON para exibir

        if guess == total:
            payout = bet * multiplier
            player.balance = float(player.balance) + payout
            result.update({
                'win': True,
                'payout': payout,
                'resultado': f'🎉 Você acertou a soma dos dados! ({total})'
            })
        else:
            player.balance = float(player.balance) - bet
            result.update({
                'payout': -bet,
                'resultado': f'Você perdeu, a soma dos dados era {total}.'
            })

    else:
        return jsonify({'error': 'unknown game'}), 400

    match = Match(player_id=player.id, game=game, bet=bet, payout=result['payout'],
                  balance_after=float(player.balance), played_at=datetime.utcnow())
    db.session.add(match)
    db.session.commit()

    if player.initial_deposit and float(player.initial_deposit) > 0 and float(player.balance) <= float(player.initial_deposit) / 2:
        result['advice'] = '⚠️ Sorte baixa: recomendamos parar por hoje.'

    result['saldo'] = float(player.balance)
    result['new_balance'] = float(player.balance)

    connected = session.get('connected_at')
    if connected:
        started = datetime.fromisoformat(connected)
        result['duration'] = int((datetime.utcnow() - started).total_seconds())

    return jsonify(result)


@app.route('/balance')
def balance():
    if not ensure_logged():
        return jsonify({'error': 'not logged'}), 403
    from models import Player
    player = Player.query.get(session['player_id'])
    return jsonify({'balance': float(player.balance)})


@app.route('/history')
def history():
    if not ensure_logged():
        return redirect(url_for('index'))
    from models import Player, Match
    player = Player.query.get(session['player_id'])
    matches = Match.query.filter_by(player_id=player.id).order_by(Match.played_at.desc()).limit(50).all()
    return render_template('history.html', username=player.name, partidas=matches)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
