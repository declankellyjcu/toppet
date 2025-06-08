# app/models.py
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import date, datetime

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    userName = db.Column(db.String(150), unique=True)
    total_wins = db.Column(db.Integer, default=0)
    notes = db.relationship('Note')
    created_groups = db.relationship('Group', foreign_keys='Group.creator_id', backref='creator')
    group_memberships = db.relationship('GroupMember', back_populates='user')
    pet_images = db.relationship('PetImage', back_populates='user')
    votes_made = db.relationship('Vote', back_populates='user_who_voted', cascade="all, delete-orphan")

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    members = db.relationship('GroupMember', back_populates='group', cascade="all, delete-orphan")
    group_pet_images = db.relationship('PetImage', backref='group_images')
    voting_rounds = db.relationship('VotingRound', back_populates='group', cascade="all, delete-orphan")

class GroupMember(db.Model):
    __tablename__ = 'group_member'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), primary_key=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=func.now())

    user = db.relationship('User', back_populates='group_memberships')
    group = db.relationship('Group', back_populates='members')

class PetImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    votes_count = db.Column(db.Integer, default=0, nullable=False)
    user = db.relationship('User', back_populates='pet_images')
    group = db.relationship('Group', back_populates='group_pet_images')
    image_votes = db.relationship('Vote', back_populates='voted_image', cascade="all, delete-orphan")
    round_id = db.Column(db.Integer, db.ForeignKey('voting_round.id'))

class Vote(db.Model):
    __tablename__ = 'vote'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    pet_image_id = db.Column(db.Integer, db.ForeignKey('pet_image.id'), primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())
    round_id = db.Column(db.Integer, db.ForeignKey('voting_round.id'))

    user_who_voted = db.relationship('User', back_populates='votes_made')
    voted_image = db.relationship('PetImage', back_populates='image_votes')
    voting_round = db.relationship('VotingRound', back_populates='votes')

class VotingRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False, default=1)
    start_time = db.Column(db.DateTime(timezone=True), default=func.now())
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    winning_image_id = db.Column(db.Integer, db.ForeignKey('pet_image.id'), nullable=True)

    group = db.relationship('Group', back_populates='voting_rounds')
    winner = db.relationship('User', foreign_keys=[winner_id])
    winning_image = db.relationship('PetImage', foreign_keys=[winning_image_id])

    # Explicitly define the foreign key relationship
    images = db.relationship('PetImage', backref='current_round_image', lazy=True, cascade="all, delete-orphan", foreign_keys=[PetImage.round_id])
    votes = db.relationship('Vote', back_populates='voting_round', lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint('group_id', 'round_number', name='_group_round_uc'),)