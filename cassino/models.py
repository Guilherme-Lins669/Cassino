# models.py
from extensions import db
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric

class Player(db.Model):
    __tablename__ = 'player'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    # Numeric é melhor para valores monetários (precisão)
    balance = db.Column(Numeric(12,2), default=0)
    initial_deposit = db.Column(Numeric(12,2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    matches = db.relationship('Match', backref='player', lazy=True)

class Match(db.Model):
    __tablename__ = 'match'
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    game = db.Column(db.String(50))
    bet = db.Column(Numeric(12,2))
    payout = db.Column(Numeric(12,2))  # positivo se ganho, negativo se perda
    balance_after = db.Column(Numeric(12,2))
    played_at = db.Column(db.DateTime, default=datetime.utcnow)
