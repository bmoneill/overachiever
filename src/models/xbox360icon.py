from . import db


class Xbox360Icon(db.Model):
    __tablename__ = "xbox360icons"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, nullable=False)
    title_id = db.Column(db.Integer, nullable=False)
    achievement_id = db.Column(db.Integer, nullable=False)
