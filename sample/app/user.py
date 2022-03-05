"""
app.user
~~~~~~~~~~~~~~

"""

from flask import Blueprint

user = Blueprint('user', __name__)

@user.get('/friend')
def friend():
    return 'HELLO MY FRIEND'