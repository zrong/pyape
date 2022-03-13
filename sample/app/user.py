"""
app.user
"""
from flask import Blueprint, abort
from webargs.flaskparser import use_args
from webargs import fields
from sqlalchemy import select

from pyape.app import gdb, logger
from app.model import User


user = Blueprint('user', __name__)


@user.get('/friend')
def friend():
    return 'HELLO MY FRIEND'


@user.get('/get')
@use_args({'id': fields.Int(required=True)}, location='query')
def get_user(args):
    id = args['id']
    userobj = gdb.session().get(User, id)
    if userobj is None:
        logger.warning(f'user {id} is not found.')
        abort(404)
    return f'User id: {userobj.id}, name: {userobj.name}'


@user.post('/set')
@use_args({'id': fields.Int(required=True), 'name': fields.Str(required=True)}, location='form')
def set_user(args):
    userobj = User(**args)
    gdb.session().add(userobj)
    gdb.session().commit()
    return f'User id: {userobj.id}, name: {userobj.name}'