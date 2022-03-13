"""
app.user_multidb

用于多数据库测试，匹配环境 --env multidb
"""
from flask import Blueprint, abort
from webargs.flaskparser import use_args
from webargs import fields
from sqlalchemy import select

from pyape.app import gdb, logger
from app.model_multidb import User1, User2


user_multidb = Blueprint('user_multidb', __name__)


@user_multidb.get('/get')
@use_args({'id': fields.Int(required=True), 'bind_key': fields.Str(required=True)}, location='query')
def get_user_db1(args):
    id = args['id']
    bind_key = args['bind_key']
    User = User1 if bind_key == 'db1' else User2
    userobj = gdb.session().get(User, id)
    if userobj is None:
        logger.warning(f'user {id} is not found in {bind_key}.')
        abort(404)
    return f'User in {bind_key} id: {userobj.id}, name: {userobj.name}'


@user_multidb.post('/set')
@use_args({'id': fields.Int(required=True), 'name': fields.Str(required=True), 'bind_key': fields.Str(required=True)}, location='form')
def set_user(args):
    bind_key = args['bind_key']
    User = User1 if bind_key == 'db1' else User2
    userobj = User(**args)
    gdb.session().add(userobj)
    gdb.session().commit()
    return f'User in {bind_key} id: {userobj.id}, name: {userobj.name}'